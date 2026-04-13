from __future__ import annotations

from datetime import datetime
from typing import Iterable

from models.notification import SystemNotification, SystemUserNotification
from models.user import SystemUser

TYPE_MAP = {
    "notice": 0,
    "announcement": 1,
    "message": 2,
}


def normalize_string_list(values: Iterable[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        normalized = str(value).strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def normalize_int_list(values: Iterable[int] | None) -> list[int]:
    result: list[int] = []
    for value in values or []:
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            continue
        if normalized not in result:
            result.append(normalized)
    return result


async def resolve_notification_user_ids(notification: SystemNotification) -> list[str]:
    if notification.scope == 0:
        rows = await SystemUser.filter(is_del=False, status=1).values_list("id", flat=True)
        return normalize_string_list(rows)

    scope_ids = normalize_string_list(notification.scope_ids)
    if not scope_ids:
        return []

    if notification.scope == 1:
        rows = await SystemUser.filter(
            is_del=False,
            status=1,
            department_id__in=scope_ids,
        ).values_list("id", flat=True)
        return normalize_string_list(rows)

    target_user_ids = [item for item in scope_ids if not item.startswith("user_type:")]
    target_user_types = normalize_int_list(
        item.split(":", 1)[1] for item in scope_ids if item.startswith("user_type:")
    )

    user_ids: list[str] = []
    if target_user_ids:
        rows = await SystemUser.filter(is_del=False, status=1, id__in=target_user_ids).values_list("id", flat=True)
        user_ids.extend(normalize_string_list(rows))

    if target_user_types:
        rows = await SystemUser.filter(is_del=False, status=1, user_type__in=target_user_types).values_list(
            "id", flat=True
        )
        user_ids.extend(normalize_string_list(rows))

    return normalize_string_list(user_ids)


async def publish_notification(
    notification: SystemNotification,
    actor_id: str | None = None,
    actor_name: str | None = None,
) -> int:
    user_ids = await resolve_notification_user_ids(notification)
    if not user_ids:
        return 0

    now = datetime.now()
    await SystemNotification.filter(id=notification.id).update(
        status=1,
        publish_time=now,
    )

    existing_user_ids = normalize_string_list(
        await SystemUserNotification.filter(
            notification_id=notification.id,
            user_id__in=user_ids,
        ).values_list("user_id", flat=True)
    )

    new_deliveries = [
        SystemUserNotification(notification_id=notification.id, user_id=user_id, delivered_at=now)
        for user_id in user_ids
        if user_id not in existing_user_ids
    ]
    if new_deliveries:
        await SystemUserNotification.bulk_create(new_deliveries)

    return len(user_ids)


async def create_login_notification(user: SystemUser) -> None:
    now = datetime.now()
    display_name = user.nickname or user.username
    title = "登录提醒"
    content = f"用户 {display_name} 于 {now.strftime('%Y-%m-%d %H:%M:%S')} 登录系统。"

    notification = await SystemNotification.create(
        title=title,
        content=content,
        type=TYPE_MAP["notice"],
        scope=2,
        scope_ids=[str(user.id)],
        priority=1,
        status=1,
        publish_time=now,
        creator_id=str(user.id),
    )
    await SystemUserNotification.create(
        notification_id=notification.id,
        user_id=user.id,
        delivered_at=now,
    )
