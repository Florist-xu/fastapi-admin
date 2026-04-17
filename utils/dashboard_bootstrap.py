from typing import Any

from models.casbin_rule import CasbinRule
from models.menus import SystemPermission
from models.role import SystemRole
from utils.access_context import is_admin_role


DASHBOARD_ROOT_MENU_CONFIG: dict[str, Any] = {
    "menu_type": 0,
    "parent_id": None,
    "name": "Dashboard",
    "title": "数据看板",
    "path": "/dashboard",
    "component": "/index/index",
    "icon": "ri:pie-chart-line",
    "order": 10,
    "min_user_type": 3,
    "remark": "可视化工作台与大屏入口",
}

DASHBOARD_CONSOLE_MENU_CONFIG: dict[str, Any] = {
    "menu_type": 0,
    "name": "Console",
    "title": "工作台",
    "path": "console",
    "component": "/dashboard/console",
    "icon": "ri:dashboard-horizontal-line",
    "keepAlive": False,
    "fixedTab": True,
    "order": 1,
    "min_user_type": 3,
    "remark": "支持拖拽、自定义布局和角色模板的首页工作台",
}

DASHBOARD_BUTTONS: list[dict[str, Any]] = [
    {
        "menu_type": 1,
        "name": "DashboardTemplateManage",
        "title": "模板管理",
        "authTitle": "模板管理",
        "authMark": "dashboard:template:manage",
        "order": 1,
        "min_user_type": 1,
    },
    {
        "menu_type": 1,
        "name": "DashboardSensitiveWidget",
        "title": "敏感组件",
        "authTitle": "敏感组件",
        "authMark": "dashboard:widget:sensitive",
        "order": 2,
        "min_user_type": 1,
    },
]

DASHBOARD_APIS: list[dict[str, Any]] = [
    {"menu_type": 2, "title": "工作台配置", "api_path": "/dashboard/workspace", "api_method": ["GET"], "order": 1, "min_user_type": 3},
    {"menu_type": 2, "title": "保存个人布局", "api_path": "/dashboard/save-layout", "api_method": ["POST"], "order": 2, "min_user_type": 3},
    {"menu_type": 2, "title": "重置个人布局", "api_path": "/dashboard/reset", "api_method": ["POST"], "order": 3, "min_user_type": 3},
    {"menu_type": 2, "title": "模板列表", "api_path": "/dashboard/templates", "api_method": ["GET"], "order": 4, "min_user_type": 1},
    {"menu_type": 2, "title": "创建模板", "api_path": "/dashboard/templates", "api_method": ["POST"], "order": 5, "min_user_type": 1},
    {"menu_type": 2, "title": "更新模板", "api_path": "/dashboard/templates/*", "api_method": ["PUT"], "order": 6, "min_user_type": 1},
    {"menu_type": 2, "title": "删除模板", "api_path": "/dashboard/templates/*", "api_method": ["DELETE"], "order": 7, "min_user_type": 1},
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
    if permission.menu_type == 1:
        return [{"v1": str(permission.id), "v2": "button"}]

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


async def ensure_dashboard_permissions() -> None:
    root_menu = await upsert_permission(
        {"name": DASHBOARD_ROOT_MENU_CONFIG["name"], "menu_type": 0},
        DASHBOARD_ROOT_MENU_CONFIG,
    )

    console_payload = {**DASHBOARD_CONSOLE_MENU_CONFIG, "parent_id": str(root_menu.id)}
    console_menu = await upsert_permission(
        {"component": DASHBOARD_CONSOLE_MENU_CONFIG["component"], "menu_type": 0},
        console_payload,
    )

    manager_permissions: list[SystemPermission] = []
    for item in DASHBOARD_BUTTONS:
        payload = {**item, "parent_id": str(console_menu.id)}
        permission = await upsert_permission({"authMark": item["authMark"], "menu_type": 1}, payload)
        manager_permissions.append(permission)

    api_permissions: list[SystemPermission] = []
    for item in DASHBOARD_APIS:
        payload = {**item, "parent_id": str(console_menu.id)}
        permission = await upsert_permission({"api_path": item["api_path"], "menu_type": 2}, payload)
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
        if is_admin_role(code) and code not in admin_role_codes:
            admin_role_codes.append(code)

    basic_permissions = [root_menu, console_menu] + [
        item for item in api_permissions if item.api_path in {"/dashboard/workspace", "/dashboard/save-layout", "/dashboard/reset"}
    ]

    for role_code in all_role_codes:
        for permission in basic_permissions:
            for policy in build_policy_payload(permission):
                await ensure_policy(role_code, policy["v1"], policy["v2"])

    for role_code in admin_role_codes:
        for permission in manager_permissions + [
            item for item in api_permissions if item.api_path not in {"/dashboard/workspace", "/dashboard/save-layout", "/dashboard/reset"}
        ]:
            for policy in build_policy_payload(permission):
                await ensure_policy(role_code, policy["v1"], policy["v2"])
