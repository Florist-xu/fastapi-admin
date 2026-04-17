from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from fields.deparment import DepartmentBase
from fields.role import RoleBase
from models.department import SystemDepartment
from models.menus import SystemPermission
from models.role import SystemRole
from models.scheduled_action import SystemScheduledAction, SystemScheduledClientEvent
from models.user import SystemUser, SystemUserRole

from apis.ai import ToolContext, assign_user_role_tool, manage_article_tool, manage_notification_tool, manage_user_tool


POLL_INTERVAL_SECONDS = 3
SCHEDULED_CLIENT_ACTION_NAMES = {"fireworks", "settings", "search", "chat", "lock", "watermark", "navigate"}
MUTATION_OPERATION_PREFIXES = (
    "user.",
    "department.",
    "role.",
    "menu.",
    "permission.",
    "notification.",
    "article.",
)

_runner_task: asyncio.Task | None = None


def is_supported_scheduled_operation(operation_type: str) -> bool:
    normalized = (operation_type or "").strip().lower()
    return normalized.startswith("client.") or normalized.startswith(MUTATION_OPERATION_PREFIXES)


async def enqueue_client_event(
    *,
    user_id: str,
    action_name: str,
    payload: dict[str, Any] | None = None,
    summary: str | None = None,
    source_task_id: str | None = None,
) -> None:
    await SystemScheduledClientEvent.create(
        user_id=user_id,
        action_name=action_name,
        payload=payload or {},
        summary=summary,
        source_task_id=source_task_id,
    )


def build_tool_context(task: SystemScheduledAction) -> ToolContext:
    return ToolContext(actor_id=task.actor_id, actor_name=task.actor_name)


def normalize_role_payload(payload: dict[str, Any], *, include_defaults: bool = False) -> dict[str, Any]:
    data = RoleBase(**payload).model_dump(exclude_none=True)
    if payload.get("department_id") is not None:
        data["department_id"] = payload.get("department_id")
    if include_defaults and "status" not in data:
        data["status"] = 1
    if include_defaults and "department_id" not in data:
        data["department_id"] = ""
    return data


def normalize_department_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return DepartmentBase(**payload).model_dump()


def normalize_menu_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from apis.menus import normalize_menu_payload as _normalize_menu_payload

    return {key: value for key, value in _normalize_menu_payload(payload).items() if value is not None}


def normalize_permission_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from apis.permission import normalize_permission_payload as _normalize_permission_payload

    return {key: value for key, value in _normalize_permission_payload(payload).items() if value is not None}


async def execute_department_operation(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    if action == "create":
        data = normalize_department_payload(payload)
        created = await SystemDepartment.create(**data)
        return {"ok": True, "message": f"已创建部门 {data['name']}", "id": str(created.id)}

    department_id = payload.get("id")
    if not department_id:
        return {"ok": False, "error": "缺少 department id"}

    department = await SystemDepartment.filter(id=department_id, is_del=False).first()
    if not department:
        return {"ok": False, "error": "部门不存在"}

    if action == "update":
        data = normalize_department_payload(payload)
        await SystemDepartment.filter(id=department_id, is_del=False).update(**data)
        return {"ok": True, "message": f"已更新部门 {department.name}"}

    if action == "delete":
        users = await SystemUser.filter(department_id=department_id, is_del=False).count()
        if users:
            return {"ok": False, "error": f"部门下仍绑定 {users} 个用户，无法删除"}
        await SystemDepartment.filter(id=department_id, is_del=False).update(is_del=True)
        return {"ok": True, "message": f"已删除部门 {department.name}"}

    return {"ok": False, "error": f"暂不支持的部门操作: {action}"}


async def execute_role_operation(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    if action == "create":
        data = normalize_role_payload(payload, include_defaults=True)
        created = await SystemRole.create(**data)
        return {"ok": True, "message": f"已创建角色 {data['name']}", "id": str(created.id)}

    role_id = payload.get("id")
    if not role_id:
        return {"ok": False, "error": "缺少 role id"}

    role = await SystemRole.filter(id=role_id, is_del=False).first()
    if not role:
        return {"ok": False, "error": "角色不存在"}

    if action == "update":
        data = normalize_role_payload(payload)
        await SystemRole.filter(id=role_id, is_del=False).update(**data)
        return {"ok": True, "message": f"已更新角色 {role.name}"}

    if action == "delete":
        bindings = await SystemUserRole.filter(role_id=role_id, is_del=False).count()
        if bindings:
            return {"ok": False, "error": f"角色下仍绑定 {bindings} 个用户，无法删除"}
        await SystemRole.filter(id=role_id).delete()
        return {"ok": True, "message": f"已删除角色 {role.name}"}

    return {"ok": False, "error": f"暂不支持的角色操作: {action}"}


async def execute_menu_operation(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    if action == "create":
        data = normalize_menu_payload(payload)
        created = await SystemPermission.create(**data)
        title = data.get("title") or data.get("name") or "菜单"
        return {"ok": True, "message": f"已创建菜单 {title}", "id": str(created.id)}

    menu_id = payload.get("id")
    if not menu_id:
        return {"ok": False, "error": "缺少 menu id"}

    menu = await SystemPermission.filter(id=menu_id, is_del=False).first()
    if not menu:
        return {"ok": False, "error": "菜单不存在"}

    title = menu.title or menu.name or "菜单"
    if action == "update":
        data = normalize_menu_payload(payload)
        await SystemPermission.filter(id=menu_id, is_del=False).update(**data)
        return {"ok": True, "message": f"已更新菜单 {title}"}

    if action == "delete":
        await SystemPermission.filter(id=menu_id, is_del=False).update(is_del=True)
        return {"ok": True, "message": f"已删除菜单 {title}"}

    return {"ok": False, "error": f"暂不支持的菜单操作: {action}"}


async def execute_permission_operation(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    from apis.permission import collect_permission_descendant_ids

    if action == "create":
        data = normalize_permission_payload(payload)
        created = await SystemPermission.create(**data)
        title = data.get("title") or data.get("name") or "权限"
        return {"ok": True, "message": f"已创建权限 {title}", "id": str(created.id)}

    permission_id = payload.get("id")
    if not permission_id:
        return {"ok": False, "error": "缺少 permission id"}

    permission = await SystemPermission.filter(id=permission_id, is_del=False).first()
    if not permission:
        return {"ok": False, "error": "权限不存在"}

    title = permission.title or permission.name or "权限"
    if action == "update":
        data = normalize_permission_payload(payload)
        await SystemPermission.filter(id=permission_id, is_del=False).update(**data)
        return {"ok": True, "message": f"已更新权限 {title}"}

    if action == "delete":
        target_ids = await collect_permission_descendant_ids(str(permission_id))
        await SystemPermission.filter(id__in=target_ids, is_del=False).update(is_del=True)
        return {"ok": True, "message": f"已删除权限 {title}"}

    return {"ok": False, "error": f"暂不支持的权限操作: {action}"}


async def execute_user_operation(task: SystemScheduledAction, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    if action == "create":
        return await manage_user_tool(action=action, fields=payload)

    if action == "update":
        user_id = payload.get("id")
        fields = {key: value for key, value in payload.items() if key != "id"}
        return await manage_user_tool(action=action, user_id=user_id, fields=fields)

    if action == "delete":
        return await manage_user_tool(action=action, user_id=payload.get("id"))

    if action == "assign_role":
        user_id = payload.get("user_id") or payload.get("id")
        role_ids = payload.get("role_ids") or []
        return await assign_user_role_tool(user_id=user_id, role_ids=role_ids)

    if action == "reset_password":
        user_id = payload.get("id")
        password = payload.get("password") or "123456"
        return await manage_user_tool(action=action, user_id=user_id, password=password, fields={"password": password})

    return {"ok": False, "error": f"暂不支持的用户操作: {action}"}


async def execute_notification_operation(task: SystemScheduledAction, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    notification_id = payload.get("id")
    fields = {key: value for key, value in payload.items() if key != "id"}
    return await manage_notification_tool(
        action=action,
        notification_id=notification_id,
        fields=fields,
        context=build_tool_context(task),
    )


async def execute_article_operation(task: SystemScheduledAction, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    article_id = payload.get("id")
    fields = {key: value for key, value in payload.items() if key != "id"}
    return await manage_article_tool(
        action=action,
        article_id=article_id,
        fields=fields,
        context=build_tool_context(task),
    )


async def execute_client_operation(task: SystemScheduledAction, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    if action not in SCHEDULED_CLIENT_ACTION_NAMES:
        return {"ok": False, "error": f"不支持的客户端动作: {action}"}
    if not task.actor_id:
        return {"ok": False, "error": "缺少调度用户，无法投递客户端动作"}
    if action == "navigate" and not payload.get("route"):
        return {"ok": False, "error": "导航动作缺少 route"}

    await enqueue_client_event(
        user_id=task.actor_id,
        action_name=action,
        payload=payload,
        summary=task.summary,
        source_task_id=str(task.id),
    )
    return {"ok": True, "message": task.summary or f"已投递客户端动作 {action}"}


async def execute_scheduled_task(task: SystemScheduledAction) -> dict[str, Any]:
    operation_type = (task.operation_type or "").strip().lower()
    payload = task.payload or {}

    if not is_supported_scheduled_operation(operation_type):
        return {"ok": False, "error": f"不支持的定时动作类型: {operation_type}"}

    if operation_type.startswith("client."):
        return await execute_client_operation(task, task.action, payload)
    if operation_type.startswith("user."):
        return await execute_user_operation(task, task.action, payload)
    if operation_type.startswith("department."):
        return await execute_department_operation(task.action, payload)
    if operation_type.startswith("role."):
        return await execute_role_operation(task.action, payload)
    if operation_type.startswith("menu."):
        return await execute_menu_operation(task.action, payload)
    if operation_type.startswith("permission."):
        return await execute_permission_operation(task.action, payload)
    if operation_type.startswith("notification."):
        return await execute_notification_operation(task, task.action, payload)
    if operation_type.startswith("article."):
        return await execute_article_operation(task, task.action, payload)

    return {"ok": False, "error": f"暂不支持的定时动作类型: {operation_type}"}


async def process_due_tasks_once() -> None:
    now = datetime.now()
    due_tasks = (
        await SystemScheduledAction.filter(is_del=False, status="pending", execute_at__lte=now)
        .order_by("execute_at", "created_at")
        .limit(20)
    )
    for task in due_tasks:
        updated = await SystemScheduledAction.filter(id=task.id, status="pending").update(
            status="running",
            started_at=now,
            error_message=None,
        )
        if not updated:
            continue

        try:
            result = await execute_scheduled_task(task)
            if result.get("ok"):
                await SystemScheduledAction.filter(id=task.id).update(
                    status="succeeded",
                    executed_at=datetime.now(),
                    result_message=result.get("message"),
                    error_message=None,
                )
                if task.actor_id and not task.operation_type.startswith("client."):
                    await enqueue_client_event(
                        user_id=task.actor_id,
                        action_name="refresh",
                        payload={"resource": task.resource},
                        summary=f"refresh:{task.resource}",
                        source_task_id=str(task.id),
                    )
            else:
                await SystemScheduledAction.filter(id=task.id).update(
                    status="failed",
                    executed_at=datetime.now(),
                    result_message=result.get("message"),
                    error_message=result.get("error") or "Task execution failed",
                )
        except Exception as exc:
            await SystemScheduledAction.filter(id=task.id).update(
                status="failed",
                executed_at=datetime.now(),
                error_message=str(exc),
            )


async def scheduled_action_runner() -> None:
    while True:
        try:
            await process_due_tasks_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def ensure_scheduled_action_runner() -> None:
    global _runner_task
    if _runner_task and not _runner_task.done():
        return
    _runner_task = asyncio.create_task(scheduled_action_runner())


async def shutdown_scheduled_action_runner() -> None:
    global _runner_task
    if not _runner_task or _runner_task.done():
        _runner_task = None
        return
    _runner_task.cancel()
    try:
        await _runner_task
    except asyncio.CancelledError:
        pass
    _runner_task = None
