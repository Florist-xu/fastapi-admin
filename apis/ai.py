import json
import os
from pathlib import Path
from typing import AsyncGenerator

import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from utils.response import ResponseUtil


aiAPI = APIRouter(prefix="/ai", tags=["ai"])


class StreamRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system_prompt: str | None = Field(default=None)
    model: str | None = Field(default=None)
    temperature: float = Field(default=0.7, ge=0, le=2)
    use_project_context: bool = Field(default=True)
    max_context_files: int = Field(default=8, ge=1, le=20)


class IntentRequest(BaseModel):
    text: str = Field(..., min_length=1)


def build_sse_event(data: dict, event: str | None = None) -> str:
    lines = []
    if event:
        lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    return "\n".join(lines) + "\n\n"


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_context_roots() -> list[Path]:
    roots = [get_project_root()]
    frontend_path = os.getenv("FRONTEND_PROJECT_PATH", r"E:\test\art-design-pro-main").strip()
    if frontend_path:
        frontend_root = Path(frontend_path)
        if frontend_root.exists():
            roots.append(frontend_root)
    return roots


def collect_candidate_files(project_root: Path) -> list[Path]:
    candidate_files: list[Path] = []

    if (project_root / "main.py").exists():
        candidate_files.append(project_root / "main.py")
    if (project_root / "config.py").exists():
        candidate_files.append(project_root / "config.py")

    for folder in (
        "apis",
        "fields",
        "models",
        "utils",
        "src/api",
        "src/router",
        "src/views",
        "src/store",
        "src/typings",
        "src/locales",
    ):
        folder_path = project_root / folder
        if folder_path.exists():
            candidate_files.extend(sorted(folder_path.rglob("*.py")))
            candidate_files.extend(sorted(folder_path.rglob("*.ts")))
            candidate_files.extend(sorted(folder_path.rglob("*.vue")))
            candidate_files.extend(sorted(folder_path.rglob("*.json")))

    return candidate_files


def collect_project_context(prompt: str, max_files: int) -> str:
    roots = get_context_roots()
    candidate_files: list[Path] = []
    for root in roots:
        candidate_files.extend(collect_candidate_files(root))

    keywords = {word.lower() for word in prompt.replace("/", " ").replace("_", " ").split() if word.strip()}
    scored_files = []

    for path in candidate_files:
        if not path.exists() or path.name.startswith("__pycache__"):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        score = 0
        file_name = path.name.lower()
        root = next((item for item in roots if path.is_relative_to(item)), None)
        if root is None:
            continue
        relative_path = path.relative_to(root).as_posix().lower()

        for keyword in keywords:
            if keyword in file_name or keyword in relative_path:
                score += 5
            score += content.lower().count(keyword)

        if score > 0:
            scored_files.append((score, root, path, content))

    if not scored_files:
        fallback_files = []
        for path in candidate_files:
            if path.exists() and path.suffix == ".py":
                root = next((item for item in roots if path.is_relative_to(item)), None)
                if root is None:
                    continue
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                fallback_files.append((0, root, path, content))
        scored_files = fallback_files

    scored_files.sort(key=lambda item: (-item[0], len(item[3])))
    selected = scored_files[:max_files]

    context_blocks = []
    project_root = get_project_root()
    for _, root, path, content in selected:
        relative_path = path.relative_to(root).as_posix()
        source_name = "frontend" if root != project_root else "backend"
        context_blocks.append(f"### Source: {source_name}\n### File: {relative_path}\n{content[:6000]}")

    return "\n\n".join(context_blocks)


def get_openai_config(model_override: str | None = None) -> tuple[str, str, str]:
    base_url = os.getenv("OPENAI_API_URL", "").rstrip("/")
    api_key = os.getenv("OPENAI_API_KEY", "")
    model = model_override or os.getenv("OPENAI_MODEL", "")
    return base_url, api_key, model


async def call_openai_json(messages: list[dict], model_override: str | None = None) -> dict:
    base_url, api_key, model = get_openai_config(model_override)
    if not base_url or not api_key or not model:
        return {}

    request_body = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "stream": False,
        "response_format": {"type": "json_object"},
    }

    try:
        timeout = httpx.Timeout(30.0, connect=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
            )
            response.raise_for_status()
            data = response.json()
            content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "{}")
            return json.loads(content)
    except Exception:
        return {}


async def detect_intent(payload: IntentRequest) -> dict:
    parsed = await call_openai_json(
        [
            {
                "role": "system",
                "content": (
                    "你是一个企业管理后台指令解析器。"
                    "请把用户输入解析为 JSON，字段固定为 action, resource, target, field, value, route。"
                    "action 只能是 navigate/create/read/update/delete/assign/unknown。"
                    "resource 只能是 user/department/role/menu/permission/unknown。"
                    "route 返回前端路由，无法确定时为空字符串。"
                    "只返回 JSON，不要解释。"
                ),
            },
            {"role": "user", "content": payload.text},
        ]
    )

    return {
        "action": parsed.get("action", "unknown"),
        "resource": parsed.get("resource", "unknown"),
        "target": parsed.get("target", ""),
        "field": parsed.get("field", ""),
        "value": parsed.get("value", ""),
        "route": parsed.get("route", ""),
    }


async def generate_text_stream(payload: StreamRequest) -> AsyncGenerator[str, None]:
    base_url, api_key, model = get_openai_config(payload.model)
    if not base_url or not api_key or not model:
        yield build_sse_event(
            {"type": "error", "message": "缺少 OPENAI_API_URL、OPENAI_API_KEY 或 OPENAI_MODEL 配置"},
            event="error",
        )
        return

    system_parts = [
        "你是当前 FastAPI 项目的开发助手。",
        "回答必须优先依据提供的项目代码上下文，不要脱离当前项目臆造接口、字段或流程。",
        "如果项目里已经有实现，要明确指出对应文件、接口路径、请求参数和返回方式。",
        "如果项目里没有实现，要明确说明缺失点，并给出基于当前项目风格的建议。",
    ]
    if payload.system_prompt:
        system_parts.append(payload.system_prompt)

    if payload.use_project_context:
        project_context = collect_project_context(payload.prompt, payload.max_context_files)
        if project_context:
            system_parts.append("以下是当前项目的相关代码上下文：\n" + project_context)

    request_body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "\n\n".join(system_parts)},
            {"role": "user", "content": payload.prompt},
        ],
        "temperature": payload.temperature,
        "stream": True,
    }

    yield build_sse_event({"type": "start", "message": "stream started", "model": model}, event="start")

    try:
        timeout = httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
            ) as response:
                if response.status_code >= 400:
                    error_text = await response.aread()
                    yield build_sse_event(
                        {
                            "type": "error",
                            "status_code": response.status_code,
                            "message": error_text.decode("utf-8", errors="ignore"),
                        },
                        event="error",
                    )
                    return

                index = 0
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        chunk_data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk_data.get("choices") or []
                    if not choices:
                        continue

                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if not content:
                        continue

                    yield build_sse_event(
                        {"type": "chunk", "index": index, "content": content, "done": False},
                        event="message",
                    )
                    index += 1
    except Exception as exc:
        yield build_sse_event({"type": "error", "message": str(exc)}, event="error")
        return

    yield build_sse_event({"type": "end", "done": True}, event="end")


@aiAPI.post("/stream", summary="流式输出")
async def stream_text(payload: StreamRequest):
    return StreamingResponse(
        generate_text_stream(payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@aiAPI.post("/intent", summary="解析聊天指令")
async def parse_intent(payload: IntentRequest):
    return ResponseUtil.success(data=await detect_intent(payload))
