from typing import Any

from tortoise.expressions import Q

from models.casbin_rule import CasbinRule
from models.menus import SystemPermission
from models.role import SystemRole
from models.user import SystemUserRole


ADMIN_ROLE_TOKENS = ("admin", "super", "root")


def dedupe_list(items: list[Any]) -> list[Any]:
    ordered: list[Any] = []
    seen: set[str] = set()
    for item in items:
        if item in (None, ""):
            continue
        marker = item if isinstance(item, (str, int, float, bool)) else str(item)
        if marker in seen:
            continue
        seen.add(str(marker))
        ordered.append(item)
    return ordered


def is_admin_role(role_code: str | None) -> bool:
    normalized = (role_code or "").strip().lower()
    return any(token in normalized for token in ADMIN_ROLE_TOKENS)


def has_permission_mark(access_context: dict[str, Any], mark: str) -> bool:
    permission_marks = access_context.get("permission_marks") or []
    return mark in permission_marks


async def get_user_role_rows(user_id: str) -> list[dict[str, Any]]:
    role_ids = await SystemUserRole.filter(user_id=user_id, is_del=False).values_list("role_id", flat=True)
    role_ids = [str(role_id) for role_id in role_ids if role_id]
    if not role_ids:
        return []

    return await SystemRole.filter(id__in=role_ids, is_del=False).values("id", "code", "name")


async def get_user_access_context(user_id: str) -> dict[str, Any]:
    role_rows = await get_user_role_rows(user_id)
    role_codes = dedupe_list([row.get("code") for row in role_rows if row.get("code")])
    role_ids = dedupe_list([str(row.get("id")) for row in role_rows if row.get("id")])

    permissions = []
    if role_codes:
        permissions = await CasbinRule.filter(v0__in=role_codes, is_del=False, ptype="p").all()

    permission_refs = {str(permission.v1) for permission in permissions if permission.v1}
    permission_map: dict[str, dict[str, Any]] = {}
    if permission_refs:
        permission_rows = await SystemPermission.filter(is_del=False).filter(
            Q(id__in=permission_refs) | Q(path__in=permission_refs) | Q(api_path__in=permission_refs)
        ).values(
            "id",
            "menu_type",
            "parent_id",
            "authMark",
            "authTitle",
            "title",
            "name",
            "path",
            "api_path",
            "api_method",
        )
        for row in permission_rows:
            keys = [row.get("id"), row.get("path"), row.get("api_path"), row.get("authMark")]
            for key in keys:
                if key:
                    permission_map[str(key)] = row

    menu_ids: list[str] = []
    button_ids: list[str] = []
    permission_marks: list[str] = []
    api_permissions: list[dict[str, str]] = []

    for permission in permissions:
        v1 = str(permission.v1 or "")
        v2 = str(permission.v2 or "")
        permission_row = permission_map.get(v1, {})

        if v2.startswith("menu"):
            menu_ids.append(str(permission_row.get("id") or v1))
            continue

        if v2.startswith("button"):
            button_ids.append(str(permission_row.get("id") or v1))
            auth_mark = permission_row.get("authMark")
            if auth_mark:
                permission_marks.append(str(auth_mark))
            continue

        api_path = permission_row.get("api_path") or v1
        if api_path:
            api_permissions.append({"path": str(api_path), "method": v2.upper() or "GET"})

    return {
        "role_ids": role_ids,
        "role_names": dedupe_list([row.get("name") for row in role_rows if row.get("name")]),
        "roles": role_codes,
        "casbin_roles": role_codes,
        "menus": dedupe_list(menu_ids),
        "buttons": dedupe_list(button_ids),
        "apis": dedupe_list(api_permissions),
        "permission_ids": dedupe_list(button_ids),
        "permission_marks": dedupe_list(permission_marks),
        "data_scope": 4,
        "sub_departments": [],
    }
