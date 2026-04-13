from typing import Any

from models.casbin_rule import CasbinRule
from models.menus import SystemPermission
from models.role import SystemRole


MODULE_CONFIGS: list[dict[str, Any]] = [
    {
        "menu": {
            "menu_type": 0,
            "parent_id": None,
            "name": "Article",
            "title": "文章管理",
            "path": "/article",
            "component": "/article/index",
            "icon": "ri:article-line",
            "authMark": "article:menu:list",
            "keepAlive": True,
            "order": 60,
            "min_user_type": 1,
            "remark": "文章管理菜单",
        },
        "buttons": [
            {
                "menu_type": 1,
                "name": "ArticleAdd",
                "title": "新增文章",
                "authTitle": "新增文章",
                "authMark": "article:btn:add",
                "order": 1,
                "min_user_type": 1,
            },
            {
                "menu_type": 1,
                "name": "ArticleUpdate",
                "title": "编辑文章",
                "authTitle": "编辑文章",
                "authMark": "article:btn:update",
                "order": 2,
                "min_user_type": 1,
            },
            {
                "menu_type": 1,
                "name": "ArticleDelete",
                "title": "删除文章",
                "authTitle": "删除文章",
                "authMark": "article:btn:delete",
                "order": 3,
                "min_user_type": 1,
            },
            {
                "menu_type": 1,
                "name": "ArticlePublish",
                "title": "发布文章",
                "authTitle": "发布文章",
                "authMark": "article:btn:publish",
                "order": 4,
                "min_user_type": 1,
            },
        ],
        "apis": [
            {"menu_type": 2, "title": "文章列表", "api_path": "/article/list", "api_method": ["GET"], "order": 1, "min_user_type": 1},
            {"menu_type": 2, "title": "文章详情", "api_path": "/article/info/*", "api_method": ["GET"], "order": 2, "min_user_type": 1},
            {"menu_type": 2, "title": "新增文章", "api_path": "/article/add", "api_method": ["POST"], "order": 3, "min_user_type": 1},
            {"menu_type": 2, "title": "编辑文章", "api_path": "/article/update/*", "api_method": ["PUT"], "order": 4, "min_user_type": 1},
            {"menu_type": 2, "title": "删除文章", "api_path": "/article/delete/*", "api_method": ["DELETE"], "order": 5, "min_user_type": 1},
            {"menu_type": 2, "title": "发布文章", "api_path": "/article/publish/*", "api_method": ["POST"], "order": 6, "min_user_type": 1},
            {"menu_type": 2, "title": "上传编辑器图片", "api_path": "/common/upload/wangeditor", "api_method": ["POST"], "order": 7, "min_user_type": 1},
        ],
    },
    {
        "menu": {
            "menu_type": 0,
            "parent_id": None,
            "name": "ArticleCategory",
            "title": "文章分类",
            "path": "/article-category",
            "component": "/article/category/index",
            "icon": "ri:folder-2-line",
            "authMark": "article-category:menu:list",
            "keepAlive": True,
            "order": 61,
            "min_user_type": 1,
            "remark": "文章分类菜单",
        },
        "buttons": [
            {"menu_type": 1, "name": "ArticleCategoryAdd", "title": "新增分类", "authTitle": "新增分类", "authMark": "article-category:btn:add", "order": 1, "min_user_type": 1},
            {"menu_type": 1, "name": "ArticleCategoryUpdate", "title": "编辑分类", "authTitle": "编辑分类", "authMark": "article-category:btn:update", "order": 2, "min_user_type": 1},
            {"menu_type": 1, "name": "ArticleCategoryDelete", "title": "删除分类", "authTitle": "删除分类", "authMark": "article-category:btn:delete", "order": 3, "min_user_type": 1},
        ],
        "apis": [
            {"menu_type": 2, "title": "分类列表", "api_path": "/article-category/list", "api_method": ["GET"], "order": 1, "min_user_type": 1},
            {"menu_type": 2, "title": "分类选项", "api_path": "/article-category/options", "api_method": ["GET"], "order": 2, "min_user_type": 1},
            {"menu_type": 2, "title": "分类详情", "api_path": "/article-category/info/*", "api_method": ["GET"], "order": 3, "min_user_type": 1},
            {"menu_type": 2, "title": "新增分类", "api_path": "/article-category/add", "api_method": ["POST"], "order": 4, "min_user_type": 1},
            {"menu_type": 2, "title": "编辑分类", "api_path": "/article-category/update/*", "api_method": ["PUT"], "order": 5, "min_user_type": 1},
            {"menu_type": 2, "title": "删除分类", "api_path": "/article-category/delete/*", "api_method": ["DELETE"], "order": 6, "min_user_type": 1},
        ],
    },
    {
        "menu": {
            "menu_type": 0,
            "parent_id": None,
            "name": "ArticleTag",
            "title": "文章标签",
            "path": "/article-tag",
            "component": "/article/tag/index",
            "icon": "ri:price-tag-3-line",
            "authMark": "article-tag:menu:list",
            "keepAlive": True,
            "order": 62,
            "min_user_type": 1,
            "remark": "文章标签菜单",
        },
        "buttons": [
            {"menu_type": 1, "name": "ArticleTagAdd", "title": "新增标签", "authTitle": "新增标签", "authMark": "article-tag:btn:add", "order": 1, "min_user_type": 1},
            {"menu_type": 1, "name": "ArticleTagUpdate", "title": "编辑标签", "authTitle": "编辑标签", "authMark": "article-tag:btn:update", "order": 2, "min_user_type": 1},
            {"menu_type": 1, "name": "ArticleTagDelete", "title": "删除标签", "authTitle": "删除标签", "authMark": "article-tag:btn:delete", "order": 3, "min_user_type": 1},
        ],
        "apis": [
            {"menu_type": 2, "title": "标签列表", "api_path": "/article-tag/list", "api_method": ["GET"], "order": 1, "min_user_type": 1},
            {"menu_type": 2, "title": "标签选项", "api_path": "/article-tag/options", "api_method": ["GET"], "order": 2, "min_user_type": 1},
            {"menu_type": 2, "title": "标签详情", "api_path": "/article-tag/info/*", "api_method": ["GET"], "order": 3, "min_user_type": 1},
            {"menu_type": 2, "title": "新增标签", "api_path": "/article-tag/add", "api_method": ["POST"], "order": 4, "min_user_type": 1},
            {"menu_type": 2, "title": "编辑标签", "api_path": "/article-tag/update/*", "api_method": ["PUT"], "order": 5, "min_user_type": 1},
            {"menu_type": 2, "title": "删除标签", "api_path": "/article-tag/delete/*", "api_method": ["DELETE"], "order": 6, "min_user_type": 1},
        ],
    },
]

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

    # Keep manual menu configuration changes made in the admin UI. Bootstrap
    # should ensure the record exists, but it should not overwrite user-tuned
    # title/icon/path/component/order/parent settings on every restart.
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


async def ensure_module_permissions(config: dict[str, Any]) -> list[SystemPermission]:
    menu_payload = config["menu"]
    menu = await upsert_permission({"name": menu_payload["name"], "menu_type": 0}, menu_payload)

    permissions = [menu]

    for item in config.get("buttons", []):
        payload = {**item, "parent_id": str(menu.id)}
        permission = await upsert_permission({"authMark": item["authMark"], "menu_type": 1}, payload)
        permissions.append(permission)

    for item in config.get("apis", []):
        payload = {**item, "parent_id": str(menu.id)}
        permission = await upsert_permission({"api_path": item["api_path"], "menu_type": 2}, payload)
        permissions.append(permission)

    return permissions


async def ensure_article_permissions() -> None:
    all_permissions: list[SystemPermission] = []
    for config in MODULE_CONFIGS:
        all_permissions.extend(await ensure_module_permissions(config))

    roles = await SystemRole.filter(is_del=False).values("code")
    target_role_codes = []
    for row in roles:
        code = (row.get("code") or "").strip()
        if not code:
            continue
        normalized = code.lower()
        if normalized in DEFAULT_ROLE_CODES or "admin" in normalized or "super" in normalized:
            target_role_codes.append(code)

    if not target_role_codes:
        return

    for role_code in target_role_codes:
        for permission in all_permissions:
            for policy in build_policy_payload(permission):
                await ensure_policy(role_code, policy["v1"], policy["v2"])
