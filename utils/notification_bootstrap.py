from typing import Any

from models.casbin_rule import CasbinRule
from models.menus import SystemPermission
from models.role import SystemRole


NOTIFICATION_MENU_CONFIG: dict[str, Any] = {
    "menu_type": 0,
    "parent_id": None,
    "name": "Notification",
    "title": "通知管理",
    "path": "notification",
    "component": "/system/notification/index",
    "icon": "ri:notification-3-line",
    "authMark": "notification:menu:list",
    "keepAlive": True,
    "order": 66,
    "min_user_type": 3,
    "remark": "站内通知、公告、消息的统一管理页面",
}

NOTIFICATION_BUTTONS: list[dict[str, Any]] = [
    {"menu_type": 1, "name": "NotificationAdd", "title": "新增通知", "authTitle": "新增通知", "authMark": "notification:btn:add", "order": 1, "min_user_type": 1},
    {"menu_type": 1, "name": "NotificationUpdate", "title": "编辑通知", "authTitle": "编辑通知", "authMark": "notification:btn:update", "order": 2, "min_user_type": 1},
    {"menu_type": 1, "name": "NotificationDelete", "title": "删除通知", "authTitle": "删除通知", "authMark": "notification:btn:delete", "order": 3, "min_user_type": 1},
    {"menu_type": 1, "name": "NotificationPublish", "title": "发布通知", "authTitle": "发布通知", "authMark": "notification:btn:publish", "order": 4, "min_user_type": 1},
    {"menu_type": 1, "name": "NotificationRevoke", "title": "撤回通知", "authTitle": "撤回通知", "authMark": "notification:btn:revoke", "order": 5, "min_user_type": 1},
]

NOTIFICATION_APIS: list[dict[str, Any]] = [
    {"menu_type": 2, "title": "通知列表", "api_path": "/notification/list", "api_method": ["GET"], "order": 1, "min_user_type": 1},
    {"menu_type": 2, "title": "通知详情", "api_path": "/notification/detail/*", "api_method": ["GET"], "order": 2, "min_user_type": 1},
    {"menu_type": 2, "title": "新增通知", "api_path": "/notification/add", "api_method": ["POST"], "order": 3, "min_user_type": 1},
    {"menu_type": 2, "title": "编辑通知", "api_path": "/notification/update/*", "api_method": ["PUT"], "order": 4, "min_user_type": 1},
    {"menu_type": 2, "title": "删除通知", "api_path": "/notification/delete/*", "api_method": ["DELETE"], "order": 5, "min_user_type": 1},
    {"menu_type": 2, "title": "发布通知", "api_path": "/notification/publish/*", "api_method": ["POST"], "order": 6, "min_user_type": 1},
    {"menu_type": 2, "title": "撤回通知", "api_path": "/notification/revoke/*", "api_method": ["POST"], "order": 7, "min_user_type": 1},
    {"menu_type": 2, "title": "我的通知列表", "api_path": "/notification/inbox", "api_method": ["GET"], "order": 8, "min_user_type": 3},
    {"menu_type": 2, "title": "我的通知概览", "api_path": "/notification/summary", "api_method": ["GET"], "order": 9, "min_user_type": 3},
    {"menu_type": 2, "title": "标记通知已读", "api_path": "/notification/read/*", "api_method": ["POST"], "order": 10, "min_user_type": 3},
    {"menu_type": 2, "title": "全部通知已读", "api_path": "/notification/read-all", "api_method": ["POST"], "order": 11, "min_user_type": 3},
]

DEFAULT_ROLE_CODES = {"r_super", "r_admin", "super_admin", "admin", "administrator", "super"}


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


async def build_menu_payload() -> dict[str, Any]:
    payload = dict(NOTIFICATION_MENU_CONFIG)
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
    permission_ref = str(permission.id)
    if permission.menu_type == 0:
        v1 = permission_ref
        v2 = "menu"
    elif permission.menu_type == 1:
        v1 = permission_ref
        v2 = "button"
    else:
        v1 = permission.api_path or permission_ref
        api_method = permission.api_method or ["GET"]
        if isinstance(api_method, list):
            v2 = str(api_method[0]).upper() if api_method else "GET"
        else:
            v2 = str(api_method).upper()

    rule = await CasbinRule.filter(v0=role_code, v1=v1, v2=v2, ptype="p").order_by("created_at").first()
    if rule:
        if rule.is_del:
            await CasbinRule.filter(id=rule.id).update(is_del=False)
        return

    await CasbinRule.create(ptype="p", v0=role_code, v1=v1, v2=v2)


async def ensure_notification_permissions() -> None:
    menu_payload = await build_menu_payload()
    menu_permission = await upsert_permission(
        {"name": NOTIFICATION_MENU_CONFIG["name"], "menu_type": 0},
        menu_payload,
    )

    button_permissions: list[SystemPermission] = []
    for item in NOTIFICATION_BUTTONS:
        payload = {**item, "parent_id": str(menu_permission.id)}
        permission = await upsert_permission(
            {"authMark": item["authMark"], "menu_type": 1},
            payload,
        )
        button_permissions.append(permission)

    api_permissions: list[SystemPermission] = []
    for item in NOTIFICATION_APIS:
        payload = {**item, "parent_id": str(menu_permission.id)}
        permission = await upsert_permission(
            {"api_path": item["api_path"], "menu_type": 2},
            payload,
        )
        api_permissions.append(permission)

    role_rows = await SystemRole.filter(is_del=False).values("code")
    all_role_codes: list[str] = []
    admin_role_codes: list[str] = []
    for row in role_rows:
        code = (row.get("code") or "").strip()
        if not code:
            continue
        if code not in all_role_codes:
            all_role_codes.append(code)
        normalized = code.lower()
        if normalized in DEFAULT_ROLE_CODES or "admin" in normalized or "super" in normalized:
            if code not in admin_role_codes:
                admin_role_codes.append(code)

    for role_code in all_role_codes:
        await ensure_policy(role_code, menu_permission)

    for role_code in admin_role_codes:
        for permission in [*button_permissions, *api_permissions]:
            await ensure_policy(role_code, permission)
