from typing import Any

from models.casbin_rule import CasbinRule
from models.menus import SystemPermission
from models.role import SystemRole


FISHTANK_MENU_CONFIG: dict[str, Any] = {
    "menu_type": 0,
    "parent_id": None,
    "name": "FishTank",
    "title": "智能鱼缸",
    "path": "/fishtank",
    "component": "/fishtank/index",
    "icon": "ri:drop-line",
    "authMark": "fishtank:menu:list",
    "keepAlive": False,
    "order": 11,
    "min_user_type": 3,
    "remark": "智能鱼缸实时状态与养护记录看板",
}

FISHTANK_APIS: list[dict[str, Any]] = [
    {
        "menu_type": 2,
        "title": "鱼缸概览",
        "api_path": "/fishtank/dashboard",
        "api_method": ["GET"],
        "order": 1,
        "min_user_type": 3,
    },
    {
        "menu_type": 2,
        "title": "更新鱼缸模拟状态",
        "api_path": "/fishtank/simulate",
        "api_method": ["PUT"],
        "order": 2,
        "min_user_type": 3,
    }
]


def merge_menu_payload(permission: SystemPermission, payload: dict[str, Any]) -> dict[str, Any]:
    update_payload = dict(payload)
    if permission.menu_type != 0:
        return update_payload

    preserve_fields = [
        "parent_id",
        "title",
        "path",
        "component",
        "icon",
        "keepAlive",
        "order",
        "remark",
        "showBadge",
        "showTextBadge",
        "isHide",
        "isHideTab",
        "link",
        "isIframe",
        "isFirstLevel",
        "fixedTab",
        "activePath",
        "isFullPage",
    ]
    for field in preserve_fields:
        current_value = getattr(permission, field, None)
        if current_value not in (None, ""):
            update_payload[field] = current_value

    return update_payload


async def upsert_permission(identity_filters: dict[str, Any], payload: dict[str, Any]) -> SystemPermission:
    permission = await SystemPermission.filter(**identity_filters).order_by("created_at").first()
    if permission:
        update_payload = merge_menu_payload(permission, payload)
        await SystemPermission.filter(id=permission.id).update(is_del=False, **update_payload)
        return await SystemPermission.get(id=permission.id)
    return await SystemPermission.create(**payload)


def build_policy_payload(permission: SystemPermission) -> list[dict[str, str]]:
    if permission.menu_type == 0:
        return [{"v1": str(permission.id), "v2": "menu"}]

    methods = permission.api_method if isinstance(permission.api_method, list) else [permission.api_method]
    api_path = permission.api_path or str(permission.id)
    return [{"v1": api_path, "v2": str(method or "GET").upper()} for method in methods]


async def ensure_policy(role_code: str, v1: str, v2: str) -> None:
    rule = await CasbinRule.filter(v0=role_code, v1=v1, v2=v2, ptype="p").order_by("created_at").first()
    if rule:
        if rule.is_del:
            await CasbinRule.filter(id=rule.id).update(is_del=False)
        return
    await CasbinRule.create(ptype="p", v0=role_code, v1=v1, v2=v2)


async def ensure_fishtank_permissions() -> None:
    menu = await upsert_permission({"name": FISHTANK_MENU_CONFIG["name"], "menu_type": 0}, FISHTANK_MENU_CONFIG)

    permissions = [menu]
    for item in FISHTANK_APIS:
        payload = {**item, "parent_id": str(menu.id)}
        permission = await upsert_permission({"api_path": item["api_path"], "menu_type": 2}, payload)
        permissions.append(permission)

    role_rows = await SystemRole.filter(is_del=False).values("code")
    role_codes = []
    for row in role_rows:
        code = (row.get("code") or "").strip()
        if code and code not in role_codes:
            role_codes.append(code)

    for role_code in role_codes:
        for permission in permissions:
            for policy in build_policy_payload(permission):
                await ensure_policy(role_code, policy["v1"], policy["v2"])
