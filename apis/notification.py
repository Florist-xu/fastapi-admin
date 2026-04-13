from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Query, Request
from tortoise.expressions import Q

from fields.notification import NotificationCreate, NotificationReadAll, NotificationUpdate
from models.notification import SystemNotification, SystemUserNotification
from utils.notification_service import normalize_string_list, publish_notification
from utils.pagination import PageParams, get_page_params
from utils.response import ResponseUtil


notificationAPI = APIRouter(prefix="/notification", tags=["notification"])

TYPE_TO_CATEGORY = {0: "notice", 1: "announcement", 2: "message"}
CATEGORY_TO_TYPE = {"notice": 0, "announcement": 1, "message": 2}


def detect_source_type(row: dict[str, Any]) -> str:
    title = (row.get("title") or "").strip()
    if int(row.get("type") or 0) == 0 and "登录" in title and "提醒" in title:
        return "login"
    return "custom"


def build_scope_payload(payload: NotificationCreate | NotificationUpdate, data: dict[str, Any]) -> dict[str, Any]:
    scope = data.get("scope")
    scope_ids = normalize_string_list(data.get("scope_ids"))

    if scope is None and "category" in data:
        data["type"] = CATEGORY_TO_TYPE.get(data.pop("category"), 2)

    if "expires_at" in data and "expire_time" not in data:
      data["expire_time"] = data.pop("expires_at")

    if scope is None:
        target_type = data.pop("target_type", None)
        target_user_ids = normalize_string_list(data.pop("target_user_ids", []))
        target_user_types = data.pop("target_user_types", []) or []
        if target_type == "user_type":
            scope = 2
            scope_ids = [f"user_type:{int(item)}" for item in target_user_types]
        elif target_type == "user":
            scope = 2
            scope_ids = target_user_ids
        else:
            scope = 0
            scope_ids = []

    data["scope"] = int(scope or 0)
    data["scope_ids"] = None if data["scope"] == 0 else scope_ids
    return data


def build_create_or_update_data(payload: NotificationCreate | NotificationUpdate) -> dict[str, Any]:
    data = payload.model_dump(
        exclude_none=True,
        by_alias=False,
        exclude={"publish_now", "summary", "category", "target_type", "target_user_ids", "target_user_types", "expires_at"},
    )

    raw = payload.model_dump(exclude_none=True, by_alias=False)
    if "type" not in data and raw.get("category") is not None:
        data["type"] = CATEGORY_TO_TYPE.get(raw.get("category"), 2)
    if "expire_time" not in data and raw.get("expires_at") is not None:
        data["expire_time"] = raw.get("expires_at")
    if "scope" not in data and "scope_ids" not in data:
        data["target_type"] = raw.get("target_type")
        data["target_user_ids"] = raw.get("target_user_ids")
        data["target_user_types"] = raw.get("target_user_types")

    return build_scope_payload(payload, data)


def build_notification_detail(item: dict[str, Any]) -> dict[str, Any]:
    notification_type = int(item.get("type") or 0)
    status = int(item.get("status") or 0)
    scope = int(item.get("scope") or 0)
    return {
        "id": str(item.get("id")),
        "title": item.get("title") or "",
        "summary": "",
        "content": item.get("content") or "",
        "category": TYPE_TO_CATEGORY.get(notification_type, "message"),
        "type": notification_type,
        "scope": scope,
        "scope_ids": normalize_string_list(item.get("scope_ids")),
        "source_type": detect_source_type(item),
        "priority": int(item.get("priority") or 0),
        "status": status,
        "publish_status": status,
        "created_by_id": item.get("creator_id"),
        "created_by_name": "",
        "publish_time": item.get("publish_time"),
        "published_at": item.get("publish_time"),
        "expire_time": item.get("expire_time"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }


async def serialize_notification_row(row: dict[str, Any]) -> dict[str, Any]:
    notification_id = str(row.get("id"))
    delivery_count = await SystemUserNotification.filter(notification_id=notification_id, is_del=False).count()
    read_count = await SystemUserNotification.filter(notification_id=notification_id, is_del=False, is_read=True).count()
    return {
        **build_notification_detail(row),
        "delivery_count": delivery_count,
        "read_count": read_count,
        "unread_count": max(delivery_count - read_count, 0),
    }


def build_inbox_item(delivery: SystemUserNotification) -> dict[str, Any]:
    notification = delivery.notification
    notification_type = int(notification.type or 0)
    return {
        "id": str(delivery.id),
        "notification_id": str(notification.id),
        "title": notification.title,
        "summary": "",
        "content": notification.content,
        "category": TYPE_TO_CATEGORY.get(notification_type, "message"),
        "type": notification_type,
        "source_type": "login" if notification_type == 0 and "登录" in notification.title else "custom",
        "priority": int(notification.priority or 0),
        "is_read": bool(delivery.is_read),
        "read_at": delivery.read_at,
        "delivered_at": delivery.delivered_at,
        "published_at": notification.publish_time,
        "expire_time": notification.expire_time,
        "created_by_name": "",
    }


def get_request_actor(request: Request) -> tuple[str | None, str | None]:
    payload = getattr(request.state, "user", {}) or {}
    return payload.get("sub"), payload.get("username")


def get_current_user_id(request: Request) -> str | None:
    payload = getattr(request.state, "user", {}) or {}
    return payload.get("sub")


@notificationAPI.get("/list", summary="通知管理列表")
async def notification_list(
    page: PageParams = Depends(get_page_params),
    keyword: str | None = Query(default=None),
    category: str | None = Query(default=None),
    type: int | None = Query(default=None),
    publish_status: int | None = Query(default=None),
    status: int | None = Query(default=None),
    source_type: str | None = Query(default=None),
):
    query = SystemNotification.filter(is_del=False)
    if keyword:
        query = query.filter(Q(title__icontains=keyword) | Q(content__icontains=keyword))
    if type is not None:
        query = query.filter(type=type)
    elif category:
        query = query.filter(type=CATEGORY_TO_TYPE.get(category, 2))

    final_status = publish_status if publish_status is not None else status
    if final_status is not None:
        query = query.filter(status=final_status)
    if source_type == "login":
        query = query.filter(type=0, title__icontains="登录")

    rows = await query.order_by("-created_at").offset(page.offset).limit(page.size).values()
    total = await query.count()
    records = [await serialize_notification_row(row) for row in rows]
    return ResponseUtil.success(data={"records": records, "total": total, "current": page.current, "size": page.size})


@notificationAPI.get("/detail/{notification_id}", summary="通知详情")
async def notification_detail(notification_id: str):
    rows = await SystemNotification.filter(id=notification_id, is_del=False).values()
    row = rows[0] if rows else None
    if not row:
        return ResponseUtil.failure(msg="通知不存在")
    return ResponseUtil.success(data=await serialize_notification_row(row))


@notificationAPI.post("/add", summary="新增通知")
async def add_notification(request: Request, payload: NotificationCreate):
    actor_id, actor_name = get_request_actor(request)
    create_data = build_create_or_update_data(payload)
    publish_now = bool(payload.publish_now or int(create_data.get("status") or 0) == 1)
    create_data["status"] = 1 if publish_now else int(create_data.get("status") or 0)

    notification = await SystemNotification.create(
        **create_data,
        creator_id=actor_id,
        publish_time=datetime.now() if publish_now else None,
    )
    if publish_now:
        delivered_count = await publish_notification(notification, actor_id=actor_id, actor_name=actor_name)
        if delivered_count == 0:
            return ResponseUtil.failure(msg="未找到可投递的用户，请检查通知范围")
    return ResponseUtil.success(msg="新增成功", data={"id": str(notification.id)})


@notificationAPI.put("/update/{notification_id}", summary="编辑通知")
async def update_notification(notification_id: str, payload: NotificationUpdate):
    notification = await SystemNotification.filter(id=notification_id, is_del=False).first()
    if not notification:
        return ResponseUtil.failure(msg="通知不存在")
    if int(notification.type or 0) == 0 and "登录" in (notification.title or ""):
        return ResponseUtil.failure(msg="登录提醒不支持编辑")

    update_data = build_create_or_update_data(payload)
    await SystemNotification.filter(id=notification_id, is_del=False).update(**update_data)
    return ResponseUtil.success(msg="修改成功")


@notificationAPI.delete("/delete/{notification_id}", summary="删除通知")
async def delete_notification(notification_id: str):
    notification = await SystemNotification.filter(id=notification_id, is_del=False).first()
    if not notification:
        return ResponseUtil.failure(msg="通知不存在")
    await SystemNotification.filter(id=notification_id, is_del=False).update(is_del=True)
    await SystemUserNotification.filter(notification_id=notification_id, is_del=False).update(is_del=True)
    return ResponseUtil.success(msg="删除成功")


@notificationAPI.post("/publish/{notification_id}", summary="发布通知")
async def publish_notification_api(notification_id: str, request: Request):
    notification = await SystemNotification.filter(id=notification_id, is_del=False).first()
    if not notification:
        return ResponseUtil.failure(msg="通知不存在")
    actor_id, actor_name = get_request_actor(request)
    delivered_count = await publish_notification(notification, actor_id=actor_id, actor_name=actor_name)
    if delivered_count == 0:
        return ResponseUtil.failure(msg="未找到可投递的用户，请检查通知范围")
    return ResponseUtil.success(msg="发布成功", data={"delivered_count": delivered_count})


@notificationAPI.post("/revoke/{notification_id}", summary="撤回通知")
async def revoke_notification(notification_id: str):
    exists = await SystemNotification.filter(id=notification_id, is_del=False).exists()
    if not exists:
        return ResponseUtil.failure(msg="通知不存在")
    await SystemNotification.filter(id=notification_id, is_del=False).update(status=2)
    return ResponseUtil.success(msg="撤回成功")


@notificationAPI.get("/inbox", summary="当前用户收件箱")
async def inbox_list(
    request: Request,
    page: PageParams = Depends(get_page_params),
    category: str | None = Query(default=None),
    unread_only: bool = Query(default=False),
    keyword: str | None = Query(default=None),
):
    user_id = get_current_user_id(request)
    if not user_id:
        return ResponseUtil.unauthorized(msg="未登录或登录已过期")

    now = datetime.now()
    query = (
        SystemUserNotification.filter(
            user_id=user_id,
            is_del=False,
            notification__is_del=False,
            notification__status=1,
        )
        .filter(Q(notification__expire_time__isnull=True) | Q(notification__expire_time__gte=now))
        .select_related("notification")
    )
    if category:
        query = query.filter(notification__type=CATEGORY_TO_TYPE.get(category, 2))
    if unread_only:
        query = query.filter(is_read=False)
    if keyword:
        query = query.filter(Q(notification__title__icontains=keyword) | Q(notification__content__icontains=keyword))

    total = await query.count()
    deliveries = await query.order_by("is_read", "-delivered_at").offset(page.offset).limit(page.size)
    records = [build_inbox_item(item) for item in deliveries]
    return ResponseUtil.success(data={"records": records, "total": total, "current": page.current, "size": page.size})


@notificationAPI.get("/summary", summary="当前用户通知概览")
async def inbox_summary(request: Request):
    user_id = get_current_user_id(request)
    if not user_id:
        return ResponseUtil.unauthorized(msg="未登录或登录已过期")

    now = datetime.now()
    unread_total = await SystemUserNotification.filter(
        user_id=user_id,
        is_del=False,
        is_read=False,
        notification__is_del=False,
        notification__status=1,
    ).filter(Q(notification__expire_time__isnull=True) | Q(notification__expire_time__gte=now)).count()

    categories: dict[str, dict[str, Any]] = {}
    for category in ["notice", "announcement", "message"]:
        notification_type = CATEGORY_TO_TYPE.get(category, 2)
        unread = await SystemUserNotification.filter(
            user_id=user_id,
            is_del=False,
            is_read=False,
            notification__is_del=False,
            notification__status=1,
            notification__type=notification_type,
        ).filter(Q(notification__expire_time__isnull=True) | Q(notification__expire_time__gte=now)).count()
        items = await (
            SystemUserNotification.filter(
                user_id=user_id,
                is_del=False,
                notification__is_del=False,
                notification__status=1,
                notification__type=notification_type,
            )
            .filter(Q(notification__expire_time__isnull=True) | Q(notification__expire_time__gte=now))
            .select_related("notification")
            .order_by("is_read", "-delivered_at")
            .limit(6)
        )
        categories[category] = {"unread": unread, "latest": [build_inbox_item(item) for item in items]}

    return ResponseUtil.success(data={"total_unread": unread_total, "categories": categories})


@notificationAPI.post("/read/{delivery_id}", summary="标记单条已读")
async def read_notification(delivery_id: str, request: Request):
    user_id = get_current_user_id(request)
    if not user_id:
        return ResponseUtil.unauthorized(msg="未登录或登录已过期")

    delivery = await SystemUserNotification.filter(id=delivery_id, user_id=user_id, is_del=False).first()
    if not delivery:
        return ResponseUtil.failure(msg="通知不存在")
    if not delivery.is_read:
        await SystemUserNotification.filter(id=delivery_id).update(is_read=True, read_at=datetime.now())
    return ResponseUtil.success(msg="已标记为已读")


@notificationAPI.post("/read-all", summary="全部标记已读")
async def read_all_notifications(request: Request, payload: NotificationReadAll | None = Body(default=None)):
    user_id = get_current_user_id(request)
    if not user_id:
        return ResponseUtil.unauthorized(msg="未登录或登录已过期")

    category = payload.category if payload else None
    query = SystemUserNotification.filter(
        user_id=user_id,
        is_del=False,
        is_read=False,
        notification__is_del=False,
    )
    if category:
        query = query.filter(notification__type=CATEGORY_TO_TYPE.get(category, 2))
    updated = await query.update(is_read=True, read_at=datetime.now())
    return ResponseUtil.success(msg="操作成功", data={"updated": updated})
