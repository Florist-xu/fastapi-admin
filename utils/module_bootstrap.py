from typing import Any

from models.casbin_rule import CasbinRule
from models.menus import SystemPermission
from models.role import SystemRole


MODULE_MENU_CONFIG: dict[str, Any] = {
    "menu": {
        "menu_type": 0,
        "parent_id": None,
        "name": "RuntimeModuleManage",
        "title": "模块管理",
        "path": "/runtime-module",
        "component": "/system/runtime-module/index",
        "icon": "ri:apps-2-line",
        "authMark": "runtime-module:menu:list",
        "keepAlive": True,
        "order": 63,
        "min_user_type": 1,
        "remark": "运行时模块管理菜单",
    },
    "buttons": [
        {"menu_type": 1, "name": "RuntimeModuleInstall", "title": "安装模块", "authTitle": "安装模块", "authMark": "runtime-module:btn:install", "order": 1, "min_user_type": 1},
        {"menu_type": 1, "name": "RuntimeModuleLoad", "title": "加载模块", "authTitle": "加载模块", "authMark": "runtime-module:btn:load", "order": 2, "min_user_type": 1},
        {"menu_type": 1, "name": "RuntimeModuleUnload", "title": "卸载模块", "authTitle": "卸载模块", "authMark": "runtime-module:btn:unload", "order": 3, "min_user_type": 1},
        {"menu_type": 1, "name": "RuntimeModuleReload", "title": "重载模块", "authTitle": "重载模块", "authMark": "runtime-module:btn:reload", "order": 4, "min_user_type": 1},
        {"menu_type": 1, "name": "RuntimeModuleConfig", "title": "配置模块", "authTitle": "配置模块", "authMark": "runtime-module:btn:config", "order": 5, "min_user_type": 1},
        {"menu_type": 1, "name": "RuntimeModuleDelete", "title": "删除模块", "authTitle": "删除模块", "authMark": "runtime-module:btn:delete", "order": 6, "min_user_type": 1},
    ],
    "apis": [
        {"menu_type": 2, "title": "模块列表", "api_path": "/runtime-module/list", "api_method": ["GET"], "order": 1, "min_user_type": 1},
        {"menu_type": 2, "title": "模块详情", "api_path": "/runtime-module/info/*", "api_method": ["GET"], "order": 2, "min_user_type": 1},
        {"menu_type": 2, "title": "模块示例", "api_path": "/runtime-module/examples", "api_method": ["GET"], "order": 3, "min_user_type": 1},
        {"menu_type": 2, "title": "上传安装模块", "api_path": "/runtime-module/install/upload", "api_method": ["POST"], "order": 4, "min_user_type": 1},
        {"menu_type": 2, "title": "安装示例模块", "api_path": "/runtime-module/install/example/*", "api_method": ["POST"], "order": 5, "min_user_type": 1},
        {"menu_type": 2, "title": "加载模块", "api_path": "/runtime-module/load/*", "api_method": ["POST"], "order": 6, "min_user_type": 1},
        {"menu_type": 2, "title": "卸载模块", "api_path": "/runtime-module/unload/*", "api_method": ["POST"], "order": 7, "min_user_type": 1},
        {"menu_type": 2, "title": "重载模块", "api_path": "/runtime-module/reload/*", "api_method": ["POST"], "order": 8, "min_user_type": 1},
        {"menu_type": 2, "title": "更新模块配置", "api_path": "/runtime-module/config/*", "api_method": ["PUT"], "order": 9, "min_user_type": 1},
        {"menu_type": 2, "title": "删除模块", "api_path": "/runtime-module/uninstall/*", "api_method": ["DELETE"], "order": 10, "min_user_type": 1},
        {"menu_type": 2, "title": "执行模块接口", "api_path": "/runtime-module/execute/*", "api_method": ["GET", "POST", "PUT", "PATCH", "DELETE"], "order": 11, "min_user_type": 1},
    ],
}

DEFAULT_ROLE_CODES = {
    "r_super",
    "r_admin",
    "super_admin",
    "admin",
    "administrator",
    "super",
}


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
    return [{"v1": api_path, "v2": method} for method in methods if method]


async def ensure_policy(role_code: str, v1: str, v2: str) -> None:
    rule = await CasbinRule.filter(v0=role_code, v1=v1, v2=v2, ptype="p").order_by("created_at").first()
    if rule:
        if rule.is_del:
            await CasbinRule.filter(id=rule.id).update(is_del=False)
        return
    await CasbinRule.create(ptype="p", v0=role_code, v1=v1, v2=v2)


async def ensure_runtime_module_permissions() -> None:
    menu_payload = MODULE_MENU_CONFIG["menu"]
    menu = await upsert_permission({"name": menu_payload["name"], "menu_type": 0}, menu_payload)

    permissions = [menu]

    for item in MODULE_MENU_CONFIG["buttons"]:
        payload = {**item, "parent_id": str(menu.id)}
        permission = await upsert_permission({"authMark": item["authMark"], "menu_type": 1}, payload)
        permissions.append(permission)

    for item in MODULE_MENU_CONFIG["apis"]:
        payload = {**item, "parent_id": str(menu.id)}
        permission = await upsert_permission({"api_path": item["api_path"], "menu_type": 2}, payload)
        permissions.append(permission)

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
        for permission in permissions:
            for policy in build_policy_payload(permission):
                await ensure_policy(role_code, policy["v1"], policy["v2"])
