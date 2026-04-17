import json
import os
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from tortoise.expressions import Q

from fields.article import ArticleCreate, ArticlePublish, ArticleUpdate
from fields.notification import NotificationCreate, NotificationUpdate
from fields.user import UserCreate, UserRoleUpdate, UserUpdate
from models.article import SystemArticle
from models.department import SystemDepartment
from models.menus import SystemPermission
from models.notification import SystemNotification, SystemUserNotification
from models.role import SystemRole
from models.user import SystemUser, SystemUserRole
from utils.notification_service import publish_notification
from utils.response import ResponseUtil
from utils.security import hash_password


aiAPI = APIRouter(prefix="/ai", tags=["ai"])

MessageRole = Literal["system", "user", "assistant"]

PROJECT_CONTEXT_FILE_LIMIT = 6000
DEFAULT_TOOL_LOOP_LIMIT = 6

RESOURCE_LABELS = {
    "user": "用户",
    "department": "部门",
    "role": "角色",
    "permission": "权限",
    "notification": "通知",
    "article": "文章",
}


class ChatMessage(BaseModel):
    role: MessageRole
    content: str = Field(..., min_length=1)


class StreamRequest(BaseModel):
    prompt: str | None = Field(default=None)
    system_prompt: str | None = Field(default=None)
    model: str | None = Field(default=None)
    temperature: float = Field(default=0.7, ge=0, le=2)
    use_project_context: bool = Field(default=True)
    max_context_files: int = Field(default=8, ge=1, le=20)
    messages: list[ChatMessage] = Field(default_factory=list)
    conversation_summary: str | None = Field(default=None)
    enable_tools: bool = Field(default=True)


class IntentRequest(BaseModel):
    text: str = Field(..., min_length=1)


@dataclass
class ToolContext:
    actor_id: str | None
    actor_name: str | None


def build_sse_event(data: dict[str, Any], event: str | None = None) -> str:
    lines: list[str] = []
    if event:
        lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(make_json_safe(data), ensure_ascii=False)}")
    return "\n".join(lines) + "\n\n"


def make_json_safe(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]
    return value


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
        if not folder_path.exists():
            continue

        for suffix in ("*.py", "*.ts", "*.vue", "*.json"):
            candidate_files.extend(sorted(folder_path.rglob(suffix)))

    return candidate_files


def collect_project_context_entries(prompt: str, max_files: int) -> list[dict[str, str]]:
    roots = get_context_roots()
    candidate_files: list[Path] = []
    for root in roots:
        candidate_files.extend(collect_candidate_files(root))

    keywords = {
        word.lower()
        for word in prompt.replace("/", " ").replace("_", " ").split()
        if word.strip()
    }
    scored_files: list[tuple[int, Path, Path, str]] = []

    for path in candidate_files:
        if not path.exists() or "__pycache__" in path.parts:
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
        lowered_content = content.lower()

        for keyword in keywords:
            if keyword in file_name or keyword in relative_path:
                score += 5
            score += lowered_content.count(keyword)

        if score > 0:
            scored_files.append((score, root, path, content))

    if not scored_files:
        fallback_files: list[tuple[int, Path, Path, str]] = []
        for path in candidate_files:
            if not path.exists() or path.suffix != ".py":
                continue
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
    project_root = get_project_root()

    entries: list[dict[str, str]] = []
    for score, root, path, content in selected:
        relative_path = path.relative_to(root).as_posix()
        source_name = "frontend" if root != project_root else "backend"
        entries.append(
            {
                "source": source_name,
                "file": relative_path,
                "score": str(score),
                "content": content[:PROJECT_CONTEXT_FILE_LIMIT],
            }
        )
    return entries


def collect_project_context(prompt: str, max_files: int) -> str:
    entries = collect_project_context_entries(prompt, max_files)
    return "\n\n".join(
        f"### Source: {entry['source']}\n### File: {entry['file']}\n{entry['content']}"
        for entry in entries
    )


def get_openai_config(model_override: str | None = None) -> tuple[str, str, str]:
    base_url = os.getenv("OPENAI_API_URL", "").rstrip("/")
    api_key = os.getenv("OPENAI_API_KEY", "")
    model = model_override or os.getenv("OPENAI_MODEL", "")
    return base_url, api_key, model


def simplify_model_schema(model_cls: type[BaseModel]) -> dict[str, Any]:
    schema = model_cls.model_json_schema()
    return {
        "required": schema.get("required", []),
        "properties": schema.get("properties", {}),
    }


def get_resource_blueprint_data(resource: str) -> dict[str, Any]:
    resource = resource.strip().lower()
    blueprints: dict[str, dict[str, Any]] = {
        "user": {
            "label": "用户",
            "routes": ["/user/list", "/user/add", "/user/update/{id}", "/user/delete/{id}", "/user/addRole"],
            "create_schema": simplify_model_schema(UserCreate),
            "update_schema": simplify_model_schema(UserUpdate),
            "role_schema": simplify_model_schema(UserRoleUpdate),
        },
        "notification": {
            "label": "通知",
            "routes": [
                "/notification/list",
                "/notification/detail/{notification_id}",
                "/notification/add",
                "/notification/update/{notification_id}",
                "/notification/delete/{notification_id}",
                "/notification/publish/{notification_id}",
                "/notification/revoke/{notification_id}",
            ],
            "create_schema": simplify_model_schema(NotificationCreate),
            "update_schema": simplify_model_schema(NotificationUpdate),
        },
        "article": {
            "label": "文章",
            "routes": [
                "/article/list",
                "/article/info/{article_id}",
                "/article/add",
                "/article/update/{article_id}",
                "/article/delete/{article_id}",
                "/article/publish/{article_id}",
            ],
            "create_schema": simplify_model_schema(ArticleCreate),
            "update_schema": simplify_model_schema(ArticleUpdate),
            "publish_schema": simplify_model_schema(ArticlePublish),
        },
        "department": {
            "label": "部门",
            "routes": ["/department/tree", "/department/list"],
            "search_fields": ["id", "name", "principal", "phone", "email", "status"],
        },
        "role": {
            "label": "角色",
            "routes": ["/role/list", "/role/permissions"],
            "search_fields": ["id", "name", "code", "description", "status", "department_id"],
        },
        "permission": {
            "label": "权限",
            "routes": ["/menu/list", "/permission/list"],
            "search_fields": ["id", "name", "title", "authTitle", "authMark", "path", "api_path", "menu_type"],
        },
    }
    return blueprints.get(resource, {"label": resource, "routes": [], "search_fields": []})


def normalize_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    chunks.append(str(item.get("text") or ""))
                elif "text" in item:
                    chunks.append(str(item.get("text") or ""))
            else:
                chunks.append(str(item))
        return "".join(chunks)
    if content is None:
        return ""
    return str(content)


def build_system_message(payload: StreamRequest, prompt_text: str) -> str:
    system_parts = [
        "你是当前 FastAPI Admin 项目的智能助手，需要优先依据项目现有代码、数据库模型和接口风格回答问题。",
        "如果用户是在咨询实现方式、字段要求、流程说明、排查原因，请直接解释，不要执行写操作。",
        "如果用户明确要求新增、修改、删除、发布、分配角色，并且信息充分，可以调用后端工具完成真实操作。",
        "如果执行操作所需参数不足，先追问缺失字段，不要擅自猜测。",
        "如果用户明确提出“创建10个测试用户”“批量造测试数据”这类批量需求，优先使用批量工具一次完成，不要反复循环调用单用户工具。",
        "工具调用结束后，请用自然、灵活、像真实助手的语气总结结果，不要机械复述。",
    ]
    if payload.system_prompt:
        system_parts.append(payload.system_prompt)
    if payload.conversation_summary:
        system_parts.append(f"以下是较早对话的压缩摘要，请把它视为真实上下文：\n{payload.conversation_summary}")
    if payload.use_project_context and prompt_text:
        project_context = collect_project_context(prompt_text, payload.max_context_files)
        if project_context:
            system_parts.append(f"以下是当前项目的相关代码上下文：\n{project_context}")
    return "\n\n".join(system_parts)


def build_model_messages(payload: StreamRequest) -> tuple[list[dict[str, Any]], str]:
    cleaned_messages = [
        {"role": message.role, "content": message.content.strip()}
        for message in payload.messages
        if message.content and message.content.strip()
    ]

    prompt_text = (payload.prompt or "").strip()
    if not prompt_text:
        user_messages = [message["content"] for message in cleaned_messages if message["role"] == "user"]
        prompt_text = user_messages[-1] if user_messages else ""

    if prompt_text and (
        not cleaned_messages
        or cleaned_messages[-1]["role"] != "user"
        or cleaned_messages[-1]["content"] != prompt_text
    ):
        cleaned_messages.append({"role": "user", "content": prompt_text})

    system_message = build_system_message(payload, prompt_text or "项目问答")
    return [{"role": "system", "content": system_message}, *cleaned_messages], prompt_text


def get_request_actor(request: Request) -> ToolContext:
    payload = getattr(request.state, "user", {}) or {}
    return ToolContext(actor_id=payload.get("sub"), actor_name=payload.get("username"))


def chunk_text(content: str, chunk_size: int = 120) -> list[str]:
    if not content:
        return []
    return [content[index : index + chunk_size] for index in range(0, len(content), chunk_size)]


def detect_batch_test_user_request(prompt_text: str) -> dict[str, Any] | None:
    text = (prompt_text or "").strip()
    if not text:
        return None

    match = re.search(r"(创建|新增|生成|造)\s*(\d{1,2})\s*个?(测试用户|测试账号|test users?|test user)", text, re.IGNORECASE)
    if not match:
        return None

    department_name_match = re.search(r"(部门|给|到)([\u4e00-\u9fa5A-Za-z0-9_ -]{2,30})(部门)", text)
    department_name = None
    if department_name_match:
        department_name = department_name_match.group(2).strip() + department_name_match.group(3)

    return {
        "count": int(match.group(2)),
        "base_username": "test_user",
        "nickname_prefix": "测试用户",
        "password": "123456",
        "department_name": department_name,
    }


def detect_batch_delete_user_request(prompt_text: str) -> dict[str, Any] | None:
    text = (prompt_text or "").strip()
    if not text or "删除" not in text or "用户" not in text:
        return None

    usernames = re.findall(r"test_user_[A-Za-z0-9_]+", text, re.IGNORECASE)
    usernames = list(dict.fromkeys(usernames))
    if not usernames:
        return None

    return {"usernames": usernames}


async def request_openai_chat_completion(
    *,
    messages: list[dict[str, Any]],
    model_override: str | None = None,
    temperature: float = 0.7,
    tools: list[dict[str, Any]] | None = None,
    response_format: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str]:
    base_url, api_key, model = get_openai_config(model_override)
    if not base_url or not api_key or not model:
        raise RuntimeError("缺少 OPENAI_API_URL、OPENAI_API_KEY 或 OPENAI_MODEL 配置")

    request_body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if tools:
        request_body["tools"] = tools
        request_body["tool_choice"] = "auto"
    if response_format:
        request_body["response_format"] = response_format

    timeout = httpx.Timeout(90.0, connect=30.0)
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
        return response.json(), model


async def iter_openai_content_chunks(
    *,
    messages: list[dict[str, Any]],
    model_override: str | None = None,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    base_url, api_key, model = get_openai_config(model_override)
    if not base_url or not api_key or not model:
        raise RuntimeError("缺少 OPENAI_API_URL、OPENAI_API_KEY 或 OPENAI_MODEL 配置")

    request_body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }

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
            response.raise_for_status()

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
                if content:
                    yield str(content)


async def call_openai_json(messages: list[dict[str, Any]], model_override: str | None = None) -> dict[str, Any]:
    try:
        data, _ = await request_openai_chat_completion(
            messages=messages,
            model_override=model_override,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
    except Exception:
        return {}

    content = normalize_message_content((((data.get("choices") or [{}])[0].get("message") or {}).get("content")))
    try:
        return json.loads(content or "{}")
    except json.JSONDecodeError:
        return {}


async def detect_intent(payload: IntentRequest) -> dict[str, Any]:
    parsed = await call_openai_json(
        [
            {
                "role": "system",
                "content": (
                    "你是企业后台指令解析器。"
                    "请把用户输入解析成 JSON，字段固定为 action、resource、target、field、value、route。"
                    "action 只能是 navigate/create/read/update/delete/assign/unknown。"
                    "resource 只能是 user/department/role/menu/permission/notification/article/unknown。"
                    "route 返回前端路由；无法确定时为空字符串。"
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


async def get_resource_blueprint_tool(resource: str) -> dict[str, Any]:
    return {"ok": True, "resource": resource, "blueprint": get_resource_blueprint_data(resource)}


async def search_project_context_tool(query: str, max_files: int = 6) -> dict[str, Any]:
    entries = collect_project_context_entries(query, max(1, min(max_files, 12)))
    return {"ok": True, "query": query, "matches": entries}


async def search_admin_records_tool(resource: str, keyword: str = "", limit: int = 8) -> dict[str, Any]:
    normalized_resource = (resource or "").strip().lower()
    normalized_keyword = (keyword or "").strip()
    limit = max(1, min(int(limit or 8), 20))

    if normalized_resource == "user":
        query = SystemUser.filter(is_del=False)
        if normalized_keyword:
            query = query.filter(
                Q(username__icontains=normalized_keyword)
                | Q(nickname__icontains=normalized_keyword)
                | Q(email__icontains=normalized_keyword)
                | Q(phone__icontains=normalized_keyword)
            )
        records = await query.order_by("-created_at").limit(limit).values(
            "id", "username", "nickname", "email", "phone", "status", "user_type", "department_id"
        )
    elif normalized_resource == "department":
        query = SystemDepartment.filter(is_del=False)
        if normalized_keyword:
            query = query.filter(
                Q(name__icontains=normalized_keyword)
                | Q(principal__icontains=normalized_keyword)
                | Q(phone__icontains=normalized_keyword)
            )
        records = await query.order_by("sort", "-created_at").limit(limit).values(
            "id", "name", "parent_id", "principal", "phone", "email", "status"
        )
    elif normalized_resource == "role":
        query = SystemRole.filter(is_del=False)
        if normalized_keyword:
            query = query.filter(
                Q(name__icontains=normalized_keyword)
                | Q(code__icontains=normalized_keyword)
                | Q(description__icontains=normalized_keyword)
            )
        records = await query.order_by("-created_at").limit(limit).values(
            "id", "name", "code", "description", "status", "department_id"
        )
    elif normalized_resource == "permission":
        query = SystemPermission.filter(is_del=False)
        if normalized_keyword:
            query = query.filter(
                Q(name__icontains=normalized_keyword)
                | Q(title__icontains=normalized_keyword)
                | Q(authTitle__icontains=normalized_keyword)
                | Q(authMark__icontains=normalized_keyword)
                | Q(path__icontains=normalized_keyword)
                | Q(api_path__icontains=normalized_keyword)
            )
        records = await query.order_by("order", "-created_at").limit(limit).values(
            "id", "menu_type", "name", "title", "authTitle", "authMark", "path", "api_path"
        )
    elif normalized_resource == "notification":
        query = SystemNotification.filter(is_del=False)
        if normalized_keyword:
            query = query.filter(Q(title__icontains=normalized_keyword) | Q(content__icontains=normalized_keyword))
        records = await query.order_by("-created_at").limit(limit).values(
            "id", "title", "type", "scope", "status", "priority", "publish_time", "expire_time"
        )
    elif normalized_resource == "article":
        query = SystemArticle.filter(is_del=False)
        if normalized_keyword:
            query = query.filter(
                Q(title__icontains=normalized_keyword)
                | Q(summary__icontains=normalized_keyword)
                | Q(content_text__icontains=normalized_keyword)
            )
        records = await query.order_by("-is_top", "sort", "-published_at", "-created_at").limit(limit).values(
            "id", "title", "summary", "status", "category_id", "category_name", "published_at"
        )
    else:
        return {"ok": False, "error": f"暂不支持搜索资源类型: {resource}"}

    return {
        "ok": True,
        "resource": normalized_resource,
        "label": RESOURCE_LABELS.get(normalized_resource, normalized_resource),
        "keyword": normalized_keyword,
        "count": len(records),
        "records": records,
    }


async def resolve_user(*, user_id: str | None = None, username: str | None = None) -> dict[str, Any] | None:
    if user_id:
        rows = await SystemUser.filter(id=user_id, is_del=False).values(
            "id", "username", "nickname", "email", "phone", "status", "user_type", "department_id"
        )
        return rows[0] if rows else None
    if username:
        rows = await SystemUser.filter(username__iexact=username, is_del=False).values(
            "id", "username", "nickname", "email", "phone", "status", "user_type", "department_id"
        )
        return rows[0] if rows else None
    return None


async def resolve_department(
    *,
    department_id: str | None = None,
    department_name: str | None = None,
    allow_default: bool = False,
) -> dict[str, Any] | None:
    if department_id:
        rows = await SystemDepartment.filter(id=department_id, is_del=False).values(
            "id", "name", "parent_id", "sort", "status"
        )
        if rows:
            return rows[0]

    normalized_name = (department_name or "").strip()
    if normalized_name:
        exact_rows = await SystemDepartment.filter(name__iexact=normalized_name, is_del=False).values(
            "id", "name", "parent_id", "sort", "status"
        )
        if exact_rows:
            return exact_rows[0]

        fuzzy_rows = await SystemDepartment.filter(name__icontains=normalized_name, is_del=False).values(
            "id", "name", "parent_id", "sort", "status"
        )
        if fuzzy_rows:
            return fuzzy_rows[0]

    if not allow_default:
        return None

    default_rows = await SystemDepartment.filter(is_del=False).order_by("sort", "created_at").values(
        "id", "name", "parent_id", "sort", "status"
    )
    return default_rows[0] if default_rows else None


async def manage_user_tool(
    *,
    action: str,
    user_id: str | None = None,
    username: str | None = None,
    fields: dict[str, Any] | None = None,
    password: str | None = None,
) -> dict[str, Any]:
    action = (action or "").strip().lower()
    fields = fields or {}

    if action == "create":
        payload = UserCreate(**fields)
        exists = await SystemUser.filter(username__iexact=payload.username, is_del=False).exists()
        if exists:
            return {"ok": False, "error": f"用户名 {payload.username} 已存在"}

        create_data = payload.model_dump()
        create_data["password"] = hash_password(payload.password)
        created = await SystemUser.create(**create_data)
        return {
            "ok": True,
            "action": action,
            "message": f"已创建用户 {payload.username}",
            "user": {"id": str(created.id), "username": payload.username},
        }

    target_user = await resolve_user(user_id=user_id, username=username)
    if not target_user:
        return {"ok": False, "error": "目标用户不存在，请先提供准确的 user_id 或 username"}

    target_user_id = str(target_user["id"])
    target_username = target_user["username"]

    if action == "update":
        payload = UserUpdate(**fields)
        update_data = payload.model_dump(exclude_none=True)
        if not update_data:
            return {"ok": False, "error": "没有可更新的字段"}
        if update_data.get("password"):
            update_data["password"] = hash_password(update_data["password"])
        await SystemUser.filter(id=target_user_id, is_del=False).update(**update_data)
        return {
            "ok": True,
            "action": action,
            "message": f"已更新用户 {target_username}",
            "updated_fields": list(update_data.keys()),
            "user": {"id": target_user_id, "username": target_username},
        }

    if action == "delete":
        await SystemUser.filter(id=target_user_id, is_del=False).update(is_del=True)
        return {
            "ok": True,
            "action": action,
            "message": f"已删除用户 {target_username}",
            "user": {"id": target_user_id, "username": target_username},
        }

    if action == "reset_password":
        next_password = password or fields.get("password") or "123456"
        await SystemUser.filter(id=target_user_id, is_del=False).update(password=hash_password(next_password))
        return {
            "ok": True,
            "action": action,
            "message": f"已重置用户 {target_username} 的密码",
            "user": {"id": target_user_id, "username": target_username},
            "default_password": next_password,
        }

    return {"ok": False, "error": f"暂不支持的用户操作: {action}"}


def sanitize_username_fragment(value: str | None, fallback: str = "test_user") -> str:
    raw = (value or "").strip().lower()
    cleaned = "".join(char if char.isalnum() else "_" for char in raw)
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or fallback


async def batch_create_users_tool(
    *,
    count: int,
    base_username: str | None = None,
    nickname_prefix: str | None = None,
    password: str = "123456",
    department_id: str | None = None,
    department_name: str | None = None,
    user_type: int = 3,
    status: int = 1,
    gender: int = 1,
) -> dict[str, Any]:
    total = max(1, min(int(count or 1), 50))
    username_prefix = sanitize_username_fragment(base_username, "test_user")
    nickname_seed = (nickname_prefix or "测试用户").strip() or "测试用户"
    batch_token = datetime.now().strftime("%m%d%H%M%S")
    department = await resolve_department(
        department_id=department_id,
        department_name=department_name,
        allow_default=True,
    )

    if not department:
        return {"ok": False, "error": "当前系统没有可用部门，无法按新增用户要求完成批量创建。"}

    created_users: list[dict[str, str]] = []
    skipped_users: list[str] = []

    for index in range(1, total + 1):
        sequence = f"{index:02d}"
        username = f"{username_prefix}_{batch_token}_{sequence}"
        exists = await SystemUser.filter(username__iexact=username, is_del=False).exists()
        if exists:
            skipped_users.append(username)
            continue

        payload = UserCreate(
            username=username,
            password=password,
            nickname=f"{nickname_seed}{sequence}",
            department_id=str(department["id"]),
            user_type=user_type,
            status=status,
            gender=gender,
        )
        create_data = payload.model_dump()
        create_data["password"] = hash_password(payload.password)
        created = await SystemUser.create(**create_data)
        created_users.append(
            {
                "id": str(created.id),
                "username": payload.username,
                "nickname": payload.nickname or payload.username,
            }
        )

    if not created_users:
        return {
            "ok": False,
            "error": "本次批量创建没有生成任何新用户，可能是用户名全部冲突。",
            "skipped": skipped_users,
        }

    return {
        "ok": True,
        "message": f"已批量创建 {len(created_users)} 个测试用户",
        "count": len(created_users),
        "default_password": password,
        "department": {"id": str(department["id"]), "name": department["name"]},
        "users": created_users,
        "skipped": skipped_users,
    }


async def batch_delete_users_tool(*, usernames: list[str]) -> dict[str, Any]:
    normalized_usernames = [item.strip() for item in usernames if str(item).strip()]
    normalized_usernames = list(dict.fromkeys(normalized_usernames))
    if not normalized_usernames:
        return {"ok": False, "error": "没有提供可删除的用户名"}

    rows = await SystemUser.filter(username__in=normalized_usernames, is_del=False).values(
        "id", "username", "nickname"
    )
    if not rows:
        return {"ok": False, "error": "没有找到可删除的目标用户"}

    user_ids = [str(item["id"]) for item in rows]
    deleted_usernames = [str(item["username"]) for item in rows]
    await SystemUser.filter(id__in=user_ids, is_del=False).update(is_del=True)
    await SystemUserRole.filter(user_id__in=user_ids, is_del=False).update(is_del=True)

    not_found = [item for item in normalized_usernames if item not in deleted_usernames]
    return {
        "ok": True,
        "message": f"已删除 {len(deleted_usernames)} 个用户",
        "deleted_count": len(deleted_usernames),
        "deleted_usernames": deleted_usernames,
        "not_found": not_found,
    }


async def assign_user_role_tool(
    *,
    user_id: str | None = None,
    username: str | None = None,
    role_ids: list[str] | None = None,
    role_codes: list[str] | None = None,
    role_names: list[str] | None = None,
) -> dict[str, Any]:
    user = await resolve_user(user_id=user_id, username=username)
    if not user:
        return {"ok": False, "error": "目标用户不存在"}

    requested_ids = [item for item in (role_ids or []) if item]
    if role_codes:
        code_rows = await SystemRole.filter(code__in=role_codes, is_del=False).values("id", "code", "name")
        requested_ids.extend([str(item["id"]) for item in code_rows])
    if role_names:
        name_rows = await SystemRole.filter(name__in=role_names, is_del=False).values("id", "code", "name")
        requested_ids.extend([str(item["id"]) for item in name_rows])

    requested_ids = [item for item in dict.fromkeys(requested_ids) if item]
    if not requested_ids:
        return {"ok": False, "error": "没有提供可分配的角色"}

    payload = UserRoleUpdate(user_id=str(user["id"]), role_ids=requested_ids)
    role_rows = await SystemRole.filter(id__in=payload.role_ids, is_del=False).values("id", "name", "code")
    valid_role_ids = {str(item["id"]) for item in role_rows}
    if not valid_role_ids:
        return {"ok": False, "error": "角色不存在"}

    existing_relations = await SystemUserRole.filter(user_id=payload.user_id).order_by("created_at").all()
    relations_by_role_id: dict[str, list[SystemUserRole]] = {}
    for relation in existing_relations:
        if relation.role_id:
            relations_by_role_id.setdefault(str(relation.role_id), []).append(relation)

    for role_id, relations in relations_by_role_id.items():
        primary_relation = relations[0]
        duplicate_relations = relations[1:]

        for duplicate_relation in duplicate_relations:
            if not duplicate_relation.is_del:
                await SystemUserRole.filter(id=duplicate_relation.id).update(is_del=True)

        if role_id in valid_role_ids:
            if primary_relation.is_del:
                await SystemUserRole.filter(id=primary_relation.id).update(is_del=False)
        elif not primary_relation.is_del:
            await SystemUserRole.filter(id=primary_relation.id).update(is_del=True)

    new_role_ids = [role_id for role_id in valid_role_ids if role_id not in relations_by_role_id]
    if new_role_ids:
        await SystemUserRole.bulk_create(
            [SystemUserRole(user_id=payload.user_id, role_id=role_id) for role_id in new_role_ids]
        )

    final_roles = await SystemUserRole.filter(user_id=payload.user_id, is_del=False).values_list("role_id", flat=True)
    role_records = await SystemRole.filter(id__in=final_roles, is_del=False).values("id", "name", "code")

    return {
        "ok": True,
        "message": f"已更新用户 {user['username']} 的角色",
        "user": {"id": str(user['id']), "username": user['username']},
        "roles": role_records,
    }


async def manage_notification_tool(
    *,
    action: str,
    notification_id: str | None = None,
    fields: dict[str, Any] | None = None,
    context: ToolContext,
) -> dict[str, Any]:
    from apis.notification import build_create_or_update_data

    action = (action or "").strip().lower()
    fields = fields or {}

    if action == "create":
        payload = NotificationCreate(**fields)
        create_data = build_create_or_update_data(payload)
        publish_now = bool(payload.publish_now or int(create_data.get("status") or 0) == 1)
        create_data["status"] = 1 if publish_now else int(create_data.get("status") or 0)
        notification = await SystemNotification.create(
            **create_data,
            creator_id=context.actor_id,
            publish_time=datetime.now() if publish_now else None,
        )
        if publish_now:
            delivered_count = await publish_notification(notification, actor_id=context.actor_id, actor_name=context.actor_name)
            if delivered_count == 0:
                return {"ok": False, "error": "通知已创建，但没有找到可投递用户，请检查通知范围"}
        return {
            "ok": True,
            "action": action,
            "message": f"已创建通知 {payload.title}",
            "notification": {"id": str(notification.id), "title": payload.title},
        }

    if not notification_id:
        return {"ok": False, "error": "缺少 notification_id"}

    notification = await SystemNotification.filter(id=notification_id, is_del=False).first()
    if not notification:
        return {"ok": False, "error": "通知不存在"}

    if action == "update":
        payload = NotificationUpdate(**fields)
        update_data = build_create_or_update_data(payload)
        if not update_data:
            return {"ok": False, "error": "没有可更新的通知字段"}
        await SystemNotification.filter(id=notification_id, is_del=False).update(**update_data)
        return {
            "ok": True,
            "action": action,
            "message": f"已更新通知 {notification.title}",
            "notification": {"id": notification_id, "title": notification.title},
            "updated_fields": list(update_data.keys()),
        }

    if action == "delete":
        await SystemNotification.filter(id=notification_id, is_del=False).update(is_del=True)
        await SystemUserNotification.filter(notification_id=notification_id, is_del=False).update(is_del=True)
        return {
            "ok": True,
            "action": action,
            "message": f"已删除通知 {notification.title}",
            "notification": {"id": notification_id, "title": notification.title},
        }

    if action == "publish":
        delivered_count = await publish_notification(notification, actor_id=context.actor_id, actor_name=context.actor_name)
        if delivered_count == 0:
            return {"ok": False, "error": "没有找到可投递的用户，请检查通知范围"}
        return {
            "ok": True,
            "action": action,
            "message": f"已发布通知 {notification.title}",
            "notification": {"id": notification_id, "title": notification.title},
            "delivered_count": delivered_count,
        }

    if action == "revoke":
        await SystemNotification.filter(id=notification_id, is_del=False).update(status=2)
        return {
            "ok": True,
            "action": action,
            "message": f"已撤回通知 {notification.title}",
            "notification": {"id": notification_id, "title": notification.title},
        }

    return {"ok": False, "error": f"暂不支持的通知操作: {action}"}


async def manage_article_tool(
    *,
    action: str,
    article_id: str | None = None,
    fields: dict[str, Any] | None = None,
    context: ToolContext,
) -> dict[str, Any]:
    from apis.article import build_article_payload

    action = (action or "").strip().lower()
    fields = fields or {}

    if action == "create":
        payload = ArticleCreate(**fields)
        data = await build_article_payload(payload.model_dump())
        data["author_id"] = context.actor_id
        data["author_name"] = context.actor_name
        created = await SystemArticle.create(**data)
        return {
            "ok": True,
            "action": action,
            "message": f"已创建文章 {payload.title}",
            "article": {"id": str(created.id), "title": payload.title},
        }

    if not article_id:
        return {"ok": False, "error": "缺少 article_id"}

    rows = await SystemArticle.filter(id=article_id, is_del=False).values()
    article = rows[0] if rows else None
    if not article:
        return {"ok": False, "error": "文章不存在"}

    if action == "update":
        payload = ArticleUpdate(**fields)
        update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not update_data:
            return {"ok": False, "error": "没有可更新的文章字段"}
        data = await build_article_payload(update_data, article)
        if context.actor_id:
            data["author_id"] = context.actor_id
        if context.actor_name:
            data["author_name"] = context.actor_name
        await SystemArticle.filter(id=article_id, is_del=False).update(**data)
        return {
            "ok": True,
            "action": action,
            "message": f"已更新文章 {article.get('title')}",
            "article": {"id": article_id, "title": article.get("title")},
            "updated_fields": list(data.keys()),
        }

    if action == "delete":
        await SystemArticle.filter(id=article_id, is_del=False).update(is_del=True)
        return {
            "ok": True,
            "action": action,
            "message": f"已删除文章 {article.get('title')}",
            "article": {"id": article_id, "title": article.get("title")},
        }

    if action == "publish":
        status = fields.get("status", 1)
        payload = ArticlePublish(status=status)
        data = await build_article_payload({"status": payload.status}, article)
        await SystemArticle.filter(id=article_id, is_del=False).update(**data)
        return {
            "ok": True,
            "action": action,
            "message": f"已更新文章发布状态 {article.get('title')}",
            "article": {"id": article_id, "title": article.get("title")},
            "status": payload.status,
        }

    return {"ok": False, "error": f"暂不支持的文章操作: {action}"}


def get_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_resource_blueprint",
                "description": "获取后台资源的字段蓝图、路由和约束，适合在执行前先确认用户、通知、文章等资源的结构。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "resource": {
                            "type": "string",
                            "enum": ["user", "department", "role", "permission", "notification", "article"],
                        }
                    },
                    "required": ["resource"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_project_context",
                "description": "搜索当前前后端项目代码上下文，适合在回答实现方式、接口字段和页面逻辑前做代码级确认。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "max_files": {"type": "integer", "minimum": 1, "maximum": 12, "default": 6},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_admin_records",
                "description": "搜索后台数据库中的用户、部门、角色、权限、通知或文章记录，用于执行操作前查找目标对象。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "resource": {
                            "type": "string",
                            "enum": ["user", "department", "role", "permission", "notification", "article"],
                        },
                        "keyword": {"type": "string", "default": ""},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 8},
                    },
                    "required": ["resource"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "manage_user",
                "description": "真实执行用户新增、修改、删除、重置密码等后端操作。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["create", "update", "delete", "reset_password"]},
                        "user_id": {"type": "string"},
                        "username": {"type": "string"},
                        "password": {"type": "string"},
                        "fields": {"type": "object"},
                    },
                    "required": ["action"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "batch_create_users",
                "description": "批量创建测试用户或批量造数账号，适合“创建10个测试用户”这类一次性需求。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer", "minimum": 1, "maximum": 50},
                        "base_username": {"type": "string"},
                        "nickname_prefix": {"type": "string"},
                        "password": {"type": "string"},
                        "department_id": {"type": "string"},
                        "department_name": {"type": "string"},
                        "user_type": {"type": "integer"},
                        "status": {"type": "integer"},
                        "gender": {"type": "integer"},
                    },
                    "required": ["count"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "batch_delete_users",
                "description": "按用户名批量删除多个用户，适合一次删除一串测试用户账号。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "usernames": {
                            "type": "array",
                            "items": {"type": "string"},
                        }
                    },
                    "required": ["usernames"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "assign_user_role",
                "description": "为指定用户分配或调整角色，支持 role_ids、role_codes 或 role_names。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"},
                        "username": {"type": "string"},
                        "role_ids": {"type": "array", "items": {"type": "string"}},
                        "role_codes": {"type": "array", "items": {"type": "string"}},
                        "role_names": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "manage_notification",
                "description": "真实执行通知的新增、修改、删除、发布和撤回。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["create", "update", "delete", "publish", "revoke"]},
                        "notification_id": {"type": "string"},
                        "fields": {"type": "object"},
                    },
                    "required": ["action"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "manage_article",
                "description": "真实执行文章的新增、修改、删除和发布状态切换。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["create", "update", "delete", "publish"]},
                        "article_id": {"type": "string"},
                        "fields": {"type": "object"},
                    },
                    "required": ["action"],
                },
            },
        },
    ]


async def execute_tool_call(
    name: str,
    arguments: dict[str, Any],
    context: ToolContext,
) -> dict[str, Any]:
    if name == "get_resource_blueprint":
        return await get_resource_blueprint_tool(resource=str(arguments.get("resource") or ""))
    if name == "search_project_context":
        return await search_project_context_tool(
            query=str(arguments.get("query") or ""),
            max_files=int(arguments.get("max_files") or 6),
        )
    if name == "search_admin_records":
        return await search_admin_records_tool(
            resource=str(arguments.get("resource") or ""),
            keyword=str(arguments.get("keyword") or ""),
            limit=int(arguments.get("limit") or 8),
        )
    if name == "manage_user":
        return await manage_user_tool(
            action=str(arguments.get("action") or ""),
            user_id=arguments.get("user_id"),
            username=arguments.get("username"),
            fields=arguments.get("fields") or {},
            password=arguments.get("password"),
        )
    if name == "batch_create_users":
        return await batch_create_users_tool(
            count=int(arguments.get("count") or 1),
            base_username=arguments.get("base_username"),
            nickname_prefix=arguments.get("nickname_prefix"),
            password=str(arguments.get("password") or "123456"),
            department_id=arguments.get("department_id"),
            department_name=arguments.get("department_name"),
            user_type=int(arguments.get("user_type") or 3),
            status=int(arguments.get("status") or 1),
            gender=int(arguments.get("gender") or 1),
        )
    if name == "batch_delete_users":
        return await batch_delete_users_tool(
            usernames=arguments.get("usernames") or [],
        )
    if name == "assign_user_role":
        return await assign_user_role_tool(
            user_id=arguments.get("user_id"),
            username=arguments.get("username"),
            role_ids=arguments.get("role_ids") or [],
            role_codes=arguments.get("role_codes") or [],
            role_names=arguments.get("role_names") or [],
        )
    if name == "manage_notification":
        return await manage_notification_tool(
            action=str(arguments.get("action") or ""),
            notification_id=arguments.get("notification_id"),
            fields=arguments.get("fields") or {},
            context=context,
        )
    if name == "manage_article":
        return await manage_article_tool(
            action=str(arguments.get("action") or ""),
            article_id=arguments.get("article_id"),
            fields=arguments.get("fields") or {},
            context=context,
        )
    return {"ok": False, "error": f"未知工具: {name}"}


async def run_tool_call_chain(
    *,
    payload: StreamRequest,
    request: Request,
) -> AsyncGenerator[str, None]:
    messages, prompt_text = build_model_messages(payload)
    _, _, model_name = get_openai_config(payload.model)
    yield build_sse_event({"type": "start", "message": "stream started", "model": model_name}, event="start")

    direct_batch_request = detect_batch_test_user_request(prompt_text)
    direct_batch_delete_request = detect_batch_delete_user_request(prompt_text)
    if payload.enable_tools and direct_batch_request:
        yield build_sse_event(
            {
                "type": "tool",
                "status": "running",
                "name": "batch_create_users",
                "arguments": direct_batch_request,
            },
            event="tool",
        )

        result = await batch_create_users_tool(
            count=int(direct_batch_request.get("count") or 1),
            base_username=direct_batch_request.get("base_username"),
            nickname_prefix=direct_batch_request.get("nickname_prefix"),
            password=str(direct_batch_request.get("password") or "123456"),
            department_name=direct_batch_request.get("department_name"),
        )

        yield build_sse_event(
            {
                "type": "tool",
                "status": "completed",
                "name": "batch_create_users",
                "result": result,
            },
            event="tool",
        )

        if result.get("ok"):
            users = result.get("users") or []
            all_usernames = "、".join(item.get("username", "") for item in users).strip("、")
            department_name = ((result.get("department") or {}).get("name") or "").strip()
            reply = (
                f"已为你创建 {result.get('count', len(users))} 个测试用户。"
                f"默认密码是 {result.get('default_password', '123456')}。"
                f"{'已绑定部门：' + department_name + '。' if department_name else ''}"
                f"{'全部账号：' + all_usernames + '。' if all_usernames else ''}"
            )
        else:
            reply = result.get("error") or "批量创建测试用户失败，请稍后重试。"

        for index, chunk in enumerate(chunk_text(reply)):
            yield build_sse_event(
                {"type": "chunk", "index": index, "content": chunk, "done": False},
                event="message",
            )
        yield build_sse_event({"type": "end", "done": True}, event="end")
        return

    if payload.enable_tools and direct_batch_delete_request:
        yield build_sse_event(
            {
                "type": "tool",
                "status": "running",
                "name": "batch_delete_users",
                "arguments": direct_batch_delete_request,
            },
            event="tool",
        )

        result = await batch_delete_users_tool(
            usernames=direct_batch_delete_request.get("usernames") or [],
        )

        yield build_sse_event(
            {
                "type": "tool",
                "status": "completed",
                "name": "batch_delete_users",
                "result": result,
            },
            event="tool",
        )

        if result.get("ok"):
            deleted_usernames = result.get("deleted_usernames") or []
            preview = "、".join(deleted_usernames[:5]).strip("、")
            not_found = result.get("not_found") or []
            reply = (
                f"已删除 {result.get('deleted_count', len(deleted_usernames))} 个用户。"
                f"{'已删除账号：' + preview + '。' if preview else ''}"
                f"{'未找到：' + '、'.join(not_found) + '。' if not_found else ''}"
            )
        else:
            reply = result.get("error") or "批量删除用户失败，请稍后重试。"

        for index, chunk in enumerate(chunk_text(reply)):
            yield build_sse_event(
                {"type": "chunk", "index": index, "content": chunk, "done": False},
                event="message",
            )
        yield build_sse_event({"type": "end", "done": True}, event="end")
        return

    if not payload.enable_tools:
        emitted = False
        async for content in iter_openai_content_chunks(
            messages=messages,
            model_override=payload.model,
            temperature=payload.temperature,
        ):
            emitted = True
            yield build_sse_event(
                {"type": "chunk", "index": 0, "content": content, "done": False},
                event="message",
            )

        if not emitted:
            fallback_text = "当前没有可返回的内容。"
            for index, chunk in enumerate(chunk_text(fallback_text)):
                yield build_sse_event(
                    {"type": "chunk", "index": index, "content": chunk, "done": False},
                    event="message",
                )

        yield build_sse_event({"type": "end", "done": True}, event="end")
        return

    tools = get_tool_specs()
    tool_context = get_request_actor(request)
    final_text = ""

    for _ in range(DEFAULT_TOOL_LOOP_LIMIT):
        response_data, _ = await request_openai_chat_completion(
            messages=messages,
            model_override=payload.model,
            temperature=payload.temperature,
            tools=tools,
        )

        choice = (response_data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        assistant_content = normalize_message_content(message.get("content"))
        tool_calls = message.get("tool_calls") or []

        if tool_calls and payload.enable_tools:
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_content,
                    "tool_calls": tool_calls,
                }
            )

            for tool_call in tool_calls:
                function_info = tool_call.get("function") or {}
                tool_name = function_info.get("name") or ""
                raw_arguments = function_info.get("arguments") or "{}"

                try:
                    tool_arguments = json.loads(raw_arguments)
                except json.JSONDecodeError:
                    tool_arguments = {}

                yield build_sse_event(
                    {
                        "type": "tool",
                        "status": "running",
                        "name": tool_name,
                        "arguments": tool_arguments,
                    },
                    event="tool",
                )

                try:
                    result = await execute_tool_call(tool_name, tool_arguments, tool_context)
                except ValidationError as exc:
                    result = {"ok": False, "error": exc.errors()}
                except Exception as exc:
                    result = {"ok": False, "error": str(exc)}

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.get("id"),
                        "name": tool_name,
                        "content": json.dumps(make_json_safe(result), ensure_ascii=False),
                    }
                )

                yield build_sse_event(
                    {
                        "type": "tool",
                        "status": "completed",
                        "name": tool_name,
                        "result": result,
                    },
                    event="tool",
                )
            continue

        final_text = assistant_content.strip()
        break
    else:
        fallback_text = "本次请求触发了过多轮工具调用，我先停在这里。你可以补充更明确的目标对象或字段后再继续。"
        for index, chunk in enumerate(chunk_text(fallback_text)):
            yield build_sse_event(
                {"type": "chunk", "index": index, "content": chunk, "done": False},
                event="message",
            )
        yield build_sse_event({"type": "end", "done": True}, event="end")
        return

    emitted = False
    try:
        index = 0
        async for content in iter_openai_content_chunks(
            messages=messages,
            model_override=payload.model,
            temperature=payload.temperature,
        ):
            emitted = True
            yield build_sse_event(
                {"type": "chunk", "index": index, "content": content, "done": False},
                event="message",
            )
            index += 1
    except Exception:
        emitted = False

    if not emitted:
        if not final_text:
            if prompt_text:
                final_text = "操作已经处理完成，但模型没有返回总结文本。"
            else:
                final_text = "当前没有可返回的内容。"

        for index, chunk in enumerate(chunk_text(final_text)):
            yield build_sse_event(
                {"type": "chunk", "index": index, "content": chunk, "done": False},
                event="message",
            )
    yield build_sse_event({"type": "end", "done": True}, event="end")
    return


async def generate_text_stream(payload: StreamRequest, request: Request) -> AsyncGenerator[str, None]:
    try:
        async for event in run_tool_call_chain(payload=payload, request=request):
            yield event
    except Exception as exc:
        yield build_sse_event({"type": "error", "message": str(exc)}, event="error")


@aiAPI.post("/stream", summary="流式输出")
async def stream_text(payload: StreamRequest, request: Request):
    return StreamingResponse(
        generate_text_stream(payload, request),
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
