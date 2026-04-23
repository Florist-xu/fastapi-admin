import json
import time
from collections import OrderedDict
from typing import Literal, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from models.operation_log import SystemOperationLog
from utils.response import ResponseUtil


operationLogAPI = APIRouter(prefix="/operation-log", tags=["operation-log"])

CHAT_OPERATION_NAME = "chat_record"
ChatAssistantScope = Literal["system", "general"]


class ChatLogCreate(BaseModel):
    user_message: str = Field(..., min_length=1)
    assistant_message: str = Field(default="")
    session_id: str = Field(..., min_length=1, max_length=64)
    session_title: str = Field(..., min_length=1, max_length=255)
    command_type: str = Field(default="chat")
    assistant_scope: ChatAssistantScope = Field(default="system")
    status: int = Field(default=1)
    cost_time: float = Field(default=0)


def detect_browser(user_agent: str) -> str:
    ua = user_agent.lower()
    if "edge" in ua:
        return "Edge"
    if "chrome" in ua:
        return "Chrome"
    if "firefox" in ua:
        return "Firefox"
    if "safari" in ua:
        return "Safari"
    return "Unknown"


def detect_os(user_agent: str) -> str:
    ua = user_agent.lower()
    if "windows" in ua:
        return "Windows"
    if "mac os" in ua or "macintosh" in ua:
        return "macOS"
    if "linux" in ua:
        return "Linux"
    if "android" in ua:
        return "Android"
    if "iphone" in ua or "ios" in ua:
        return "iOS"
    return "Unknown"


def parse_json(value: str) -> dict:
    try:
        return json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}


@operationLogAPI.post("/chat")
async def create_chat_log(payload: ChatLogCreate, request: Request):
    started_at = time.perf_counter()
    user_state = getattr(request.state, "user", {}) or {}
    user_agent = request.headers.get("user-agent", "")

    log = await SystemOperationLog.create(
        operation_name=CHAT_OPERATION_NAME,
        operation_type=1,
        request_path=request.url.path,
        request_method=request.method,
        host=request.client.host if request.client else "",
        location="",
        user_agent=user_agent,
        browser=detect_browser(user_agent),
        os=detect_os(user_agent),
        request_params=json.dumps(
            {
                "session_id": payload.session_id,
                "session_title": payload.session_title,
                "user_message": payload.user_message,
                "command_type": payload.command_type,
                "assistant_scope": payload.assistant_scope,
            },
            ensure_ascii=False,
        ),
        response_result=json.dumps(
            {
                "assistant_message": payload.assistant_message,
            },
            ensure_ascii=False,
        ),
        status=payload.status,
        cost_time=payload.cost_time or round(time.perf_counter() - started_at, 4),
        operator_id=user_state.get("sub"),
    )
    return ResponseUtil.success(data={"id": str(log.id)})


@operationLogAPI.get("/chat/session-list")
async def get_chat_sessions(request: Request, keyword: Optional[str] = None):
    user_state = getattr(request.state, "user", {}) or {}
    query = SystemOperationLog.filter(is_del=False, operation_name=CHAT_OPERATION_NAME).order_by("-created_at")

    operator_id = user_state.get("sub")
    if operator_id:
        query = query.filter(operator_id=operator_id)

    if keyword:
        query = query.filter(request_params__icontains=keyword)

    items = await query
    sessions: OrderedDict[str, dict] = OrderedDict()

    for item in items:
        request_data = parse_json(item.request_params)
        session_id = request_data.get("session_id")
        if not session_id:
            continue

        session = sessions.get(session_id)
        if not session:
            sessions[session_id] = {
                "session_id": session_id,
                "session_title": request_data.get("session_title") or request_data.get("user_message") or "未命名问题",
                "created_at": item.created_at,
                "updated_at": item.updated_at,
                "latest_message": request_data.get("user_message") or "",
                "latest_scope": request_data.get("assistant_scope") or "system",
                "message_count": 1,
                "cost_time": item.cost_time,
            }
            continue

        session["message_count"] += 1
        session["latest_scope"] = request_data.get("assistant_scope") or session["latest_scope"]

    return ResponseUtil.success(data=list(sessions.values()))


@operationLogAPI.get("/chat/session/{session_id}")
async def get_chat_session_detail(session_id: str, request: Request):
    user_state = getattr(request.state, "user", {}) or {}
    query = SystemOperationLog.filter(
        is_del=False,
        operation_name=CHAT_OPERATION_NAME,
        request_params__icontains=f'"session_id": "{session_id}"',
    ).order_by("created_at")

    operator_id = user_state.get("sub")
    if operator_id:
        query = query.filter(operator_id=operator_id)

    items = await query
    data = []

    for item in items:
        request_data = parse_json(item.request_params)
        response_data = parse_json(item.response_result)
        data.append(
            {
                "id": str(item.id),
                "session_id": session_id,
                "session_title": request_data.get("session_title") or request_data.get("user_message") or "未命名问题",
                "created_at": item.created_at,
                "user_message": request_data.get("user_message", ""),
                "assistant_message": response_data.get("assistant_message", ""),
                "command_type": request_data.get("command_type", "chat"),
                "assistant_scope": request_data.get("assistant_scope", "system"),
                "status": item.status,
                "cost_time": item.cost_time,
            }
        )

    return ResponseUtil.success(data=data)


@operationLogAPI.delete("/chat/session/{session_id}")
async def delete_chat_session(session_id: str, request: Request):
    user_state = getattr(request.state, "user", {}) or {}
    query = SystemOperationLog.filter(
        is_del=False,
        operation_name=CHAT_OPERATION_NAME,
        request_params__icontains=f'"session_id": "{session_id}"',
    )

    operator_id = user_state.get("sub")
    if operator_id:
        query = query.filter(operator_id=operator_id)

    exists = await query.exists()
    if not exists:
        return ResponseUtil.failure(msg="会话不存在")

    await query.update(is_del=True)
    return ResponseUtil.success(msg="删除成功")


@operationLogAPI.delete("/chat")
async def clear_chat_logs(request: Request):
    user_state = getattr(request.state, "user", {}) or {}
    query = SystemOperationLog.filter(is_del=False, operation_name=CHAT_OPERATION_NAME)

    operator_id = user_state.get("sub")
    if operator_id:
        query = query.filter(operator_id=operator_id)

    await query.update(is_del=True)
    return ResponseUtil.success(msg="清空成功")
