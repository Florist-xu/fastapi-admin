from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator

from models.scheduled_action import SystemScheduledAction, SystemScheduledClientEvent
from utils.response import ResponseUtil
from utils.scheduled_action_runner import is_supported_scheduled_operation


scheduledActionAPI = APIRouter(prefix="/scheduled-action", tags=["scheduled-action"])
APP_TIMEZONE = ZoneInfo("Asia/Shanghai")


class ScheduleActionPayload(BaseModel):
    operation_type: str = Field(..., min_length=3, max_length=80)
    execute_at: datetime
    summary: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("operation_type")
    @classmethod
    def validate_operation_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not is_supported_scheduled_operation(normalized):
            raise ValueError(f"Unsupported scheduled operation: {normalized}")
        return normalized


def get_request_actor(request: Request) -> tuple[str | None, str | None]:
    payload = getattr(request.state, "user", {}) or {}
    return payload.get("sub"), payload.get("username")


def normalize_execute_at(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(APP_TIMEZONE).replace(tzinfo=None)


@scheduledActionAPI.post("/schedule", summary="Create scheduled action")
async def schedule_action(request: Request, payload: ScheduleActionPayload):
    actor_id, actor_name = get_request_actor(request)
    now = datetime.now()
    execute_at = normalize_execute_at(payload.execute_at)
    if execute_at <= now:
        return ResponseUtil.failure(msg="执行时间必须晚于当前时间")

    resource, action = payload.operation_type.split(".", 1)
    task = await SystemScheduledAction.create(
        actor_id=actor_id,
        actor_name=actor_name,
        operation_type=payload.operation_type,
        resource=resource,
        action=action,
        summary=payload.summary,
        payload=payload.payload,
        execute_at=execute_at,
    )
    return ResponseUtil.success(
        msg="已创建倒计时任务",
        data={
            "id": str(task.id),
            "operation_type": payload.operation_type,
            "execute_at": execute_at,
            "summary": payload.summary,
            "status": task.status,
        },
    )


@scheduledActionAPI.get("/client-events", summary="Poll pending client events")
async def poll_client_events(request: Request):
    actor_id, _ = get_request_actor(request)
    if not actor_id:
        return ResponseUtil.unauthorized(msg="未登录或登录已过期")

    events = (
        await SystemScheduledClientEvent.filter(
            user_id=actor_id,
            is_del=False,
            consumed_at__isnull=True,
        )
        .order_by("available_at", "created_at")
        .limit(50)
        .values(
            "id",
            "action_name",
            "summary",
            "payload",
            "source_task_id",
            "available_at",
            "created_at",
        )
    )
    event_ids = [str(item["id"]) for item in events if item.get("id")]
    if event_ids:
        await SystemScheduledClientEvent.filter(id__in=event_ids, consumed_at__isnull=True).update(
            consumed_at=datetime.now()
        )

    records = [
        {
            "id": str(item.get("id")),
            "action_name": item.get("action_name"),
            "summary": item.get("summary"),
            "payload": item.get("payload") or {},
            "source_task_id": item.get("source_task_id"),
            "available_at": item.get("available_at"),
            "created_at": item.get("created_at"),
        }
        for item in events
    ]
    return ResponseUtil.success(data={"records": records, "total": len(records)})
