from typing import Any

from models.casbin_rule import CasbinRule
from models.menus import SystemPermission
from models.role import SystemRole


FORM_DESIGNER_MENU_CONFIG: dict[str, Any] = {
    "menu_type": 0,
    "parent_id": None,
    "name": "FormDesigner",
    "title": "动态表单设计器",
    "path": "form-designer",
    "component": "/system/form-designer/index",
    "icon": "ri:layout-grid-line",
    "authMark": "form-designer:menu:list",
    "keepAlive": True,
    "order": 64,
    "min_user_type": 1,
    "remark": "拖拽生成动态表单的设计器页面",
}

DEFAULT_ROLE_CODES = {
    "r_super",
    "r_admin",
    "super_admin",
    "admin",
    "administrator",
    "super",
}


async def upsert_permission(identity_filters: dict[str, Any], payload: dict[str, Any]) -> SystemPermission:
    permission = await SystemPermission.filter(**identity_filters).order_by("created_at").first()
    if permission:
        update_payload = dict(payload)
        if update_payload.get("parent_id") is None and permission.parent_id:
            update_payload["parent_id"] = permission.parent_id
        await SystemPermission.filter(id=permission.id).update(is_del=False, **update_payload)
        return await SystemPermission.get(id=permission.id)
    return await SystemPermission.create(**payload)


async def build_menu_payload() -> dict[str, Any]:
    payload = dict(FORM_DESIGNER_MENU_CONFIG)
    system_menu = await (
        SystemPermission.filter(is_del=False, menu_type=0)
        .filter(path="/system")
        .order_by("created_at")
        .first()
    )

    if system_menu:
        payload["parent_id"] = str(system_menu.id)

    return payload


async def ensure_policy(role_code: str, permission: SystemPermission) -> None:
    menu_ref = str(permission.id)
    rule = await CasbinRule.filter(
        v0=role_code,
        v1=menu_ref,
        v2="menu",
        ptype="p",
    ).order_by("created_at").first()
    if rule:
        if rule.is_del:
            await CasbinRule.filter(id=rule.id).update(is_del=False)
        return

    await CasbinRule.create(ptype="p", v0=role_code, v1=menu_ref, v2="menu")


async def ensure_form_designer_permissions() -> None:
    menu_payload = await build_menu_payload()
    permission = await upsert_permission(
        {"name": FORM_DESIGNER_MENU_CONFIG["name"], "menu_type": 0},
        menu_payload,
    )

    roles = await SystemRole.filter(is_del=False).values("code")
    target_role_codes: list[str] = []
    for row in roles:
        code = (row.get("code") or "").strip()
        if not code:
            continue
        normalized = code.lower()
        if normalized in DEFAULT_ROLE_CODES or "admin" in normalized or "super" in normalized:
            target_role_codes.append(code)

    for role_code in target_role_codes:
        await ensure_policy(role_code, permission)
