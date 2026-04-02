from typing import Any

from fastapi import APIRouter, Body, Query

from models.menus import SystemPermission
from utils.response import ResponseUtil


permissionAPI = APIRouter(prefix="/permission", tags=["permission"])


def normalize_permission_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "menu_type": payload.get("menu_type", 0),
        "parent_id": payload.get("parent_id"),
        "name": payload.get("name"),
        "title": payload.get("title"),
        "path": payload.get("path"),
        "component": payload.get("component"),
        "icon": payload.get("icon"),
        "api_path": payload.get("api_path"),
        "api_method": payload.get("api_method"),
        "data_scope": payload.get("data_scope", 4),
        "showBadge": payload.get("showBadge"),
        "showTextBadge": payload.get("showTextBadge"),
        "isHide": payload.get("isHide"),
        "isHideTab": payload.get("isHideTab"),
        "link": payload.get("link"),
        "isIframe": payload.get("isIframe"),
        "keepAlive": payload.get("keepAlive"),
        "isFirstLevel": payload.get("isFirstLevel"),
        "fixedTab": payload.get("fixedTab"),
        "activePath": payload.get("activePath"),
        "isFullPage": payload.get("isFullPage"),
        "order": payload.get("order", 999),
        "authTitle": payload.get("authTitle"),
        "authMark": payload.get("authMark"),
        "min_user_type": payload.get("min_user_type", 3),
        "remark": payload.get("remark"),
    }


async def collect_permission_descendant_ids(permission_id: str) -> list[str]:
    rows = await SystemPermission.filter(is_del=False).values("id", "parent_id")
    children_map: dict[str, list[str]] = {}
    for row in rows:
        parent_id = row.get("parent_id")
        if not parent_id:
            continue
        children_map.setdefault(str(parent_id), []).append(str(row["id"]))

    result: list[str] = []
    stack = [permission_id]
    visited: set[str] = set()

    while stack:
        current_id = stack.pop()
        if current_id in visited:
            continue
        visited.add(current_id)
        result.append(current_id)
        stack.extend(children_map.get(current_id, []))

    return result


@permissionAPI.get("/tree")
async def tree():
    rows = await SystemPermission.filter(is_del=False).order_by("order", "created_at").values()
    node_map = {str(row["id"]): {**row, "children": []} for row in rows}

    tree_data = []
    for row in node_map.values():
        parent_id = row.get("parent_id")
        parent_key = str(parent_id) if parent_id else None
        if parent_key and parent_key in node_map:
            node_map[parent_key]["children"].append(row)
            node_map[parent_key]["children"].sort(key=lambda x: x.get("order", 0))
        else:
            tree_data.append(row)

    tree_data.sort(key=lambda x: x.get("order", 0))
    return ResponseUtil.success(data=tree_data)


@permissionAPI.get("/info/{permission_id}")
async def permission_info(permission_id: str):
    permission = await SystemPermission.filter(id=permission_id, is_del=False).values()
    if not permission:
        return ResponseUtil.failure(msg="权限不存在")
    return ResponseUtil.success(data=permission)


@permissionAPI.get("/buttons/{menu_id}")
async def buttons(menu_id: str):
    rows = (
        await SystemPermission.filter(parent_id=menu_id, is_del=False, menu_type=1)
        .order_by("order", "created_at")
        .values()
    )
    return ResponseUtil.success(data=rows)


@permissionAPI.get("/list")
async def list_permissions(
    pid: str | None = Query(default=None),
    menu_type: int | None = Query(default=None),
    name: str | None = Query(default=None),
    title: str | None = Query(default=None),
    api_path: str | None = Query(default=None),
    api_method: str | None = Query(default=None),
):
    filters: dict[str, Any] = {"is_del": False}
    if pid:
        filters["parent_id"] = pid
    if menu_type is not None:
        filters["menu_type"] = menu_type

    queryset = SystemPermission.filter(**filters)
    if name:
        queryset = queryset.filter(name__icontains=name)
    if title:
        queryset = queryset.filter(title__icontains=title)
    if api_path:
        queryset = queryset.filter(api_path__icontains=api_path)
    if api_method:
        queryset = queryset.filter(api_method__contains=[api_method.upper()])

    rows = await queryset.order_by("order", "created_at").values()
    return ResponseUtil.success(data=rows)


@permissionAPI.post("/add")
async def add_permission(payload: dict = Body(...)):
    data = {k: v for k, v in normalize_permission_payload(payload).items() if v is not None}
    created = await SystemPermission.create(**data)
    return ResponseUtil.success(msg="新增成功", data={"id": str(created.id)})


@permissionAPI.post("/button/add")
async def add_button_permission(payload: dict = Body(...)):
    button_payload = {"menu_type": 1, **payload}
    data = {k: v for k, v in normalize_permission_payload(button_payload).items() if v is not None}
    created = await SystemPermission.create(**data)
    return ResponseUtil.success(msg="新增成功", data={"id": str(created.id)})


@permissionAPI.put("/update/{permission_id}")
async def update_permission(permission_id: str, payload: dict = Body(...)):
    data = {k: v for k, v in normalize_permission_payload(payload).items() if v is not None}
    exists = await SystemPermission.filter(id=permission_id, is_del=False).exists()
    if not exists:
        return ResponseUtil.failure(msg="权限不存在")
    await SystemPermission.filter(id=permission_id, is_del=False).update(**data)
    return ResponseUtil.success(msg="修改成功")


@permissionAPI.put("/button/update/{permission_id}")
async def update_button_permission(permission_id: str, payload: dict = Body(...)):
    button_payload = {"menu_type": 1, **payload}
    data = {k: v for k, v in normalize_permission_payload(button_payload).items() if v is not None}
    exists = await SystemPermission.filter(id=permission_id, is_del=False).exists()
    if not exists:
        return ResponseUtil.failure(msg="权限不存在")
    await SystemPermission.filter(id=permission_id, is_del=False).update(**data)
    return ResponseUtil.success(msg="修改成功")


@permissionAPI.delete("/delete/{permission_id}")
async def delete_permission(permission_id: str):
    exists = await SystemPermission.filter(id=permission_id, is_del=False).exists()
    if not exists:
        return ResponseUtil.failure(msg="权限不存在")
    target_ids = await collect_permission_descendant_ids(permission_id)
    await SystemPermission.filter(id__in=target_ids, is_del=False).update(is_del=True)
    return ResponseUtil.success(msg="删除成功")


@permissionAPI.delete("/button/delete/{permission_id}")
async def delete_button_permission(permission_id: str):
    exists = await SystemPermission.filter(id=permission_id, is_del=False).exists()
    if not exists:
        return ResponseUtil.failure(msg="权限不存在")
    await SystemPermission.filter(id=permission_id, is_del=False).update(is_del=True)
    return ResponseUtil.success(msg="删除成功")
