from typing import Any

from fastapi import APIRouter, Body, Request

from models.casbin_rule import CasbinRule
from models.menus import SystemPermission
from models.user import SystemUserRole
from models.role import SystemRole
from utils.response import ResponseUtil


menusAPI = APIRouter(prefix="/menus", tags=["menus"])


def normalize_menu_payload(payload: dict[str, Any]) -> dict[str, Any]:
    meta = payload.get("meta") or {}
    return {
        "menu_type": payload.get("menu_type", 0),
        "parent_id": payload.get("parent_id"),
        "name": payload.get("name"),
        "path": payload.get("path"),
        "component": payload.get("component"),
        "title": payload.get("title") or meta.get("title"),
        "icon": payload.get("icon") or meta.get("icon"),
        "showBadge": payload.get("showBadge") if "showBadge" in payload else meta.get("showBadge"),
        "showTextBadge": payload.get("showTextBadge") or meta.get("showTextBadge"),
        "isHide": payload.get("isHide") if "isHide" in payload else meta.get("isHide"),
        "isHideTab": payload.get("isHideTab") if "isHideTab" in payload else meta.get("isHideTab"),
        "link": payload.get("link") or meta.get("link"),
        "isIframe": payload.get("isIframe") if "isIframe" in payload else meta.get("isIframe"),
        "keepAlive": payload.get("keepAlive") if "keepAlive" in payload else meta.get("keepAlive"),
        "isFirstLevel": payload.get("isFirstLevel") if "isFirstLevel" in payload else meta.get("isFirstLevel"),
        "fixedTab": payload.get("fixedTab") if "fixedTab" in payload else meta.get("fixedTab"),
        "activePath": payload.get("activePath") or meta.get("activePath"),
        "isFullPage": payload.get("isFullPage") if "isFullPage" in payload else meta.get("isFullPage"),
        "order": payload.get("order") if payload.get("order") is not None else meta.get("sort", 999),
        "authTitle": payload.get("authTitle"),
        "authMark": payload.get("authMark"),
        "min_user_type": payload.get("min_user_type", 3),
        "remark": payload.get("remark"),
    }


def build_menu_meta(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": row.get("title") or row.get("name") or "",
        "icon": row.get("icon"),
        "showBadge": row.get("showBadge"),
        "showTextBadge": row.get("showTextBadge"),
        "isHide": row.get("isHide"),
        "isHideTab": row.get("isHideTab"),
        "link": row.get("link"),
        "isIframe": row.get("isIframe"),
        "keepAlive": row.get("keepAlive"),
        "isFirstLevel": row.get("isFirstLevel"),
        "fixedTab": row.get("fixedTab"),
        "activePath": row.get("activePath"),
        "isFullPage": row.get("isFullPage"),
        "auth": [row["authMark"]] if row.get("authMark") and row.get("menu_type") == 0 else None,
        "authList": [],
        "minUserType": row.get("min_user_type", 3),
    }


def convert_menu_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id")),
        "parent_id": str(row.get("parent_id")) if row.get("parent_id") else None,
        "name": row.get("name") or row.get("title") or f"Menu{row.get('id')}",
        "path": row.get("path") or "",
        "component": row.get("component"),
        "meta": build_menu_meta(row),
        "order": row.get("order", 999),
        "children": [],
    }


def build_menu_tree(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    node_map: dict[str, dict[str, Any]] = {}
    tree: list[dict[str, Any]] = []

    for row in rows:
        if row.get("menu_type") != 0:
            continue
        node = convert_menu_row(row)
        node_map[node["id"]] = node

    for row in rows:
        if row.get("menu_type") != 1 or not row.get("parent_id"):
            continue
        parent_id = str(row["parent_id"])
        parent = node_map.get(parent_id)
        if not parent:
            continue
        auth_title = row.get("authTitle") or row.get("title") or row.get("name")
        auth_mark = row.get("authMark")
        if auth_title and auth_mark:
            auth_list = parent["meta"].get("authList")
            if not isinstance(auth_list, list):
                auth_list = []
                parent["meta"]["authList"] = auth_list
            auth_list.append({"title": auth_title, "authMark": auth_mark})

    for node in node_map.values():
        parent_id = node.get("parent_id")
        if parent_id and parent_id in node_map:
            node_map[parent_id]["children"].append(node)
        else:
            tree.append(node)

    def sort_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nodes.sort(key=lambda item: item.get("order", 999))
        for item in nodes:
            if item.get("children"):
                sort_nodes(item["children"])
            else:
                item.pop("children", None)
            if not item["meta"].get("authList"):
                item["meta"].pop("authList", None)
            if not item["meta"].get("auth"):
                item["meta"].pop("auth", None)
        return nodes

    return sort_nodes(tree)


@menusAPI.get("/list")
async def list_menus(request: Request):
    payload = getattr(request.state, "user", {}) or {}
    # print(payload,"测试")
    user_id = payload.get("sub")
    if not user_id:
        return ResponseUtil.unauthorized(msg="未登录或登录已过期")

    role_ids = await SystemUserRole.filter(user_id=user_id, is_del=False).values_list("role_id", flat=True)
    role_ids = [str(role_id) for role_id in role_ids if role_id]
    if not role_ids:
        return ResponseUtil.success(data={"records": [], "total": 0, "current": 1, "size": 0})

    role_codes = await SystemRole.filter(id__in=role_ids, is_del=False).values_list("code", flat=True)
    role_codes = [code for code in role_codes if code]
    if not role_codes:
        return ResponseUtil.success(data={"records": [], "total": 0, "current": 1, "size": 0})

    menu_refs = await CasbinRule.filter(
        is_del=False,
        ptype="p",
        v0__in=role_codes,
        v2__startswith="menu",
    ).values_list("v1", flat=True)
    menu_ids = {str(ref) for ref in menu_refs if ref}
    if not menu_ids:
        return ResponseUtil.success(data={"records": [], "total": 0, "current": 1, "size": 0})

    all_menu_rows = await (
        SystemPermission.filter(is_del=False, menu_type__in=[0, 1])
        .order_by("order", "created_at")
        .values()
    )
    row_map = {str(row["id"]): row for row in all_menu_rows if row.get("id")}

    visible_menu_ids = set(menu_ids)
    for menu_id in list(menu_ids):
        current = row_map.get(menu_id)
        while current and current.get("parent_id"):
            parent_id = str(current["parent_id"])
            if parent_id in visible_menu_ids:
                break
            visible_menu_ids.add(parent_id)
            current = row_map.get(parent_id)

    rows = [
        row
        for row in all_menu_rows
        if (
            str(row.get("id")) in visible_menu_ids
            and row.get("menu_type") == 0
        ) or (
            row.get("menu_type") == 1
            and row.get("parent_id")
            and str(row.get("parent_id")) in visible_menu_ids
        )
    ]
    records = build_menu_tree(rows)
    return ResponseUtil.success(
        data={
            "records": records,
            "total": len(records),
            "current": 1,
            "size": len(records),
        }
    )


@menusAPI.post("/add")
async def add_menu(payload: dict = Body(...)):
    data = {k: v for k, v in normalize_menu_payload(payload).items() if v is not None}
    await SystemPermission.create(**data)
    return ResponseUtil.success(msg="新增成功")


@menusAPI.put("/update/{menu_id}")
async def update_menu(menu_id: str, payload: dict = Body(...)):
    data = {k: v for k, v in normalize_menu_payload(payload).items() if v is not None}
    await SystemPermission.filter(id=menu_id, is_del=False).update(**data)
    return ResponseUtil.success(msg="修改成功")


@menusAPI.delete("/delete/{menu_id}")
async def delete_menu(menu_id: str):
    await SystemPermission.filter(id=menu_id, is_del=False).update(is_del=True)
    return ResponseUtil.success(msg="删除成功")
