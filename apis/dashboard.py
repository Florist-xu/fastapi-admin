from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Request
from models.article import SystemArticle
from models.dashboard import (
    SystemDashboardRoleTemplate,
    SystemDashboardTemplate,
    SystemDashboardUserConfig,
)
from models.notification import SystemNotification, SystemUserNotification
from models.role import SystemRole
from models.user import SystemUser, SystemUserRole

from fields.dashboard import DashboardLayoutSave, DashboardTemplateCreate, DashboardTemplateUpdate
from utils.access_context import get_user_access_context, has_permission_mark, is_admin_role
from utils.response import ResponseUtil


dashboardAPI = APIRouter(prefix="/dashboard", tags=["dashboard"])

WIDGET_LIBRARY: list[dict[str, Any]] = [
    {
        "type": "stats",
        "title": "经营指标",
        "description": "聚合的核心统计卡片，适合老板一眼看全局",
        "category": "overview",
        "default_span": 12,
    },
    {
        "type": "line",
        "title": "趋势折线",
        "description": "查看近一周新增量与活跃变化趋势",
        "category": "chart",
        "default_span": 6,
    },
    {
        "type": "bar",
        "title": "柱状排行",
        "description": "展示栏目、团队或模块的排名对比",
        "category": "chart",
        "default_span": 6,
    },
    {
        "type": "pie",
        "title": "结构分布",
        "description": "查看角色或业务结构占比",
        "category": "chart",
        "default_span": 6,
    },
    {
        "type": "todo",
        "title": "待办清单",
        "description": "突出当前最需要跟进的事项",
        "category": "task",
        "default_span": 6,
    },
    {
        "type": "announcement",
        "title": "公告动态",
        "description": "展示最新公告、系统提醒与发布动态",
        "category": "feed",
        "default_span": 6,
    },
    {
        "type": "quick-actions",
        "title": "快捷操作",
        "description": "将高频入口收纳成角色专属捷径",
        "category": "action",
        "default_span": 6,
    },
    {
        "type": "data-list",
        "title": "数据列表",
        "description": "用列表方式承载最近发布、异常或跟进数据",
        "category": "feed",
        "default_span": 12,
    },
    {
        "type": "sensitive",
        "title": "敏感经营洞察",
        "description": "仅对授权角色开放的敏感数据组件",
        "category": "secure",
        "default_span": 6,
        "permission_mark": "dashboard:widget:sensitive",
    },
]

DEFAULT_LAYOUT: list[dict[str, Any]] = [
    {
        "id": "widget-stats",
        "type": "stats",
        "title": "经营指标",
        "description": "角色首页默认模板的指标总览",
        "span": 12,
        "visible": True,
        "collapsed": False,
    },
    {
        "id": "widget-line",
        "type": "line",
        "title": "趋势折线",
        "description": "近一周关键数据走势",
        "span": 6,
        "visible": True,
        "collapsed": False,
    },
    {
        "id": "widget-bar",
        "type": "bar",
        "title": "柱状排行",
        "description": "模块排名与转化对比",
        "span": 6,
        "visible": True,
        "collapsed": False,
    },
    {
        "id": "widget-pie",
        "type": "pie",
        "title": "结构分布",
        "description": "角色构成和结构占比",
        "span": 6,
        "visible": True,
        "collapsed": False,
    },
    {
        "id": "widget-quick-actions",
        "type": "quick-actions",
        "title": "快捷操作",
        "description": "角色高频动作捷径",
        "span": 6,
        "visible": True,
        "collapsed": False,
    },
    {
        "id": "widget-announcement",
        "type": "announcement",
        "title": "公告动态",
        "description": "最近发布与系统提醒",
        "span": 6,
        "visible": True,
        "collapsed": False,
    },
    {
        "id": "widget-todo",
        "type": "todo",
        "title": "待办清单",
        "description": "当前最需要跟进的工作项",
        "span": 6,
        "visible": True,
        "collapsed": False,
    },
    {
        "id": "widget-data-list",
        "type": "data-list",
        "title": "数据列表",
        "description": "最近发布内容与业务线索",
        "span": 12,
        "visible": True,
        "collapsed": False,
    },
    {
        "id": "widget-sensitive",
        "type": "sensitive",
        "title": "敏感经营洞察",
        "description": "高权限用户的敏感数据面板",
        "span": 6,
        "visible": False,
        "collapsed": False,
    },
]


def clone_default_layout() -> list[dict[str, Any]]:
    return deepcopy(DEFAULT_LAYOUT)


def dedupe_list(items: list[Any]) -> list[Any]:
    ordered: list[Any] = []
    seen: set[Any] = set()
    for item in items:
        if item in (None, ""):
            continue
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def clamp_span(value: Any) -> int:
    try:
        span = int(value)
    except (TypeError, ValueError):
        span = 6
    return max(3, min(12, span))


def get_allowed_widgets(access_context: dict[str, Any]) -> list[dict[str, Any]]:
    permission_marks = set(access_context.get("permission_marks") or [])
    return [
        deepcopy(widget)
        for widget in WIDGET_LIBRARY
        if not widget.get("permission_mark") or widget["permission_mark"] in permission_marks
    ]


def sanitize_layout(layout: Any, access_context: dict[str, Any]) -> list[dict[str, Any]]:
    allowed_widgets = get_allowed_widgets(access_context)
    widget_map = {widget["type"]: widget for widget in allowed_widgets}
    default_map = {item["type"]: item for item in clone_default_layout() if item["type"] in widget_map}

    normalized: list[dict[str, Any]] = []
    if isinstance(layout, list):
        for raw_item in layout:
            if not isinstance(raw_item, dict):
                continue
            widget_type = str(raw_item.get("type") or "").strip()
            if not widget_type or widget_type not in widget_map or widget_type not in default_map:
                continue
            default_item = default_map[widget_type]
            normalized.append(
                {
                    "id": str(raw_item.get("id") or default_item["id"]),
                    "type": widget_type,
                    "title": str(raw_item.get("title") or default_item["title"]),
                    "description": str(raw_item.get("description") or default_item["description"]),
                    "span": clamp_span(raw_item.get("span", default_item["span"])),
                    "visible": bool(raw_item.get("visible", default_item.get("visible", True))),
                    "collapsed": bool(raw_item.get("collapsed", default_item.get("collapsed", False))),
                    "config": raw_item.get("config") if isinstance(raw_item.get("config"), dict) else {},
                }
            )

    existing_types = {item["type"] for item in normalized}
    for default_item in clone_default_layout():
        if default_item["type"] in widget_map and default_item["type"] not in existing_types:
            normalized.append(default_item)

    return normalized


async def build_dashboard_metrics(user_id: str, access_context: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)
    date_labels = [(today_start - timedelta(days=offset)).strftime("%m-%d") for offset in range(6, -1, -1)]

    total_users = await SystemUser.filter(is_del=False).count()
    total_roles = await SystemRole.filter(is_del=False).count()
    total_articles = await SystemArticle.filter(is_del=False).count()
    published_articles = await SystemArticle.filter(is_del=False, status=1).count()
    total_notifications = await SystemNotification.filter(is_del=False).count()
    unread_notifications = await SystemUserNotification.filter(
        is_del=False, user_id=user_id, is_read=False
    ).count()

    article_trend: list[int] = []
    login_trend: list[int] = []
    for offset in range(6, -1, -1):
        start_at = today_start - timedelta(days=offset)
        end_at = start_at + timedelta(days=1)
        article_count = await SystemArticle.filter(
            is_del=False, created_at__gte=start_at, created_at__lt=end_at
        ).count()
        login_count = await SystemNotification.filter(
            is_del=False, type=0, created_at__gte=start_at, created_at__lt=end_at
        ).count()
        article_trend.append(article_count)
        login_trend.append(login_count)

    role_rows = await SystemRole.filter(is_del=False).values("id", "name")
    role_distribution = []
    for role_row in role_rows[:5]:
        member_count = await SystemUserRole.filter(is_del=False, role_id=role_row["id"]).count()
        role_distribution.append({"name": role_row["name"], "value": member_count})
    role_distribution = [item for item in role_distribution if item["value"] > 0] or [
        {"name": "普通用户", "value": max(total_users, 1)}
    ]

    latest_announcements = await SystemNotification.filter(is_del=False).order_by(
        "-publish_time", "-created_at"
    ).values("id", "title", "type", "publish_time")
    latest_articles = await SystemArticle.filter(is_del=False).order_by(
        "-published_at", "-created_at"
    ).values("id", "title", "author_name", "status", "published_at", "view_count", "category_name")

    personalized_user_count = await SystemDashboardUserConfig.filter(is_del=False).exclude(layout=None).count()

    return {
        "stats": {
            "headline": {
                "title": "角色化首页工作台",
                "subtitle": "拖拽结束自动保存，角色模板统一下发，个人定制互不影响。",
            },
            "cards": [
                {"label": "用户总量", "value": total_users, "trend": "+12%", "tone": "ocean"},
                {"label": "角色数量", "value": total_roles, "trend": "+3", "tone": "sun"},
                {"label": "已发布内容", "value": published_articles, "trend": f"{total_articles} 总条目", "tone": "forest"},
                {"label": "我的未读提醒", "value": unread_notifications, "trend": f"{total_notifications} 条通知", "tone": "violet"},
            ],
        },
        "line": {
            "x_axis": date_labels,
            "series": [
                {"name": "内容新增", "data": article_trend},
                {"name": "登录活跃", "data": login_trend},
            ],
        },
        "bar": {
            "x_axis": ["内容中心", "权限中心", "通知中心", "表单设计", "运行模块"],
            "series": [92, 87, 79, 68, 61],
        },
        "pie": {"total": total_users, "series": role_distribution},
        "announcement": [
            {
                "id": str(item.get("id")),
                "title": item.get("title") or "未命名公告",
                "time": (item.get("publish_time") or now).strftime("%m-%d %H:%M")
                if isinstance(item.get("publish_time"), datetime)
                else "刚刚",
                "tag": "公告" if item.get("type") == 1 else "系统",
            }
            for item in latest_announcements[:5]
        ]
        or [
            {
                "id": "notice-default",
                "title": "当前暂无公告，模板管理仍可正常演示。",
                "time": "刚刚",
                "tag": "系统",
            }
        ],
        "todo": [
            {"id": "todo-template", "title": "校准角色默认模板", "time": "今天 10:00", "status": "processing", "owner": "超级管理员"},
            {"id": "todo-chart", "title": "补齐销售与转化看板图表", "time": "今天 14:00", "status": "pending", "owner": "数据运营"},
            {"id": "todo-review", "title": "确认敏感组件授权范围", "time": "今天 17:30", "status": "pending", "owner": "风控负责人"},
        ],
        "quick_actions": [
            {"label": "用户管理", "path": "/system/user", "icon": "ri:user-3-line"},
            {"label": "角色权限", "path": "/system/role", "icon": "ri:shield-user-line"},
            {"label": "站内通知", "path": "/system/notification", "icon": "ri:notification-3-line"},
            {"label": "数据大屏", "path": "/dashboard/screen", "icon": "ri:presentation-line"},
        ],
        "data_list": [
            {
                "id": str(item.get("id")),
                "title": item.get("title") or "未命名内容",
                "category": item.get("category_name") or "未分类",
                "author": item.get("author_name") or "系统",
                "status": "已发布" if item.get("status") == 1 else "草稿",
                "views": item.get("view_count") or 0,
            }
            for item in latest_articles[:6]
        ]
        or [
            {
                "id": "article-default",
                "title": "当前暂无文章数据，可在内容中心新增后自动回流到工作台。",
                "category": "演示数据",
                "author": "系统",
                "status": "提示",
                "views": 0,
            }
        ],
        "sensitive": [
            {"label": "模板覆盖率", "value": f"{min(98, 65 + total_roles * 3)}%", "hint": "角色已配置默认模板的覆盖比例"},
            {"label": "个性化用户数", "value": str(personalized_user_count), "hint": "已在默认模板上进行个人定制的用户"},
            {
                "label": "敏感组件访问角色",
                "value": str(len([code for code in access_context.get("casbin_roles", []) if is_admin_role(code) or code in {"finance", "ceo"}])),
                "hint": "具备敏感洞察组件访问权限的角色数量",
            },
        ],
    }


async def get_role_template_for_user(role_ids: list[str]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not role_ids:
        return None, []

    bindings = await SystemDashboardRoleTemplate.filter(role_id__in=role_ids, is_del=False).order_by(
        "priority", "-updated_at", "-created_at"
    ).values("id", "role_id", "template_id", "priority")
    if not bindings:
        return None, []

    template_ids = dedupe_list([binding["template_id"] for binding in bindings if binding.get("template_id")])
    template_rows = await SystemDashboardTemplate.filter(id__in=template_ids, is_del=False, status=1).values()
    template_map = {str(row["id"]): row for row in template_rows if row.get("id")}
    active_bindings = [binding for binding in bindings if str(binding.get("template_id")) in template_map]
    if not active_bindings:
        return None, []

    role_rows = await SystemRole.filter(id__in=role_ids, is_del=False).values("id", "name", "code")
    role_map = {str(row["id"]): row for row in role_rows if row.get("id")}

    binding_details = []
    for binding in active_bindings:
        role_detail = role_map.get(str(binding["role_id"]), {})
        template_detail = template_map.get(str(binding["template_id"]), {})
        binding_details.append(
            {
                "role_id": str(binding["role_id"]),
                "role_name": role_detail.get("name") or "",
                "role_code": role_detail.get("code") or "",
                "priority": binding.get("priority", 100),
                "template_id": str(binding["template_id"]),
                "template_name": template_detail.get("name") or "",
            }
        )

    selected_binding = active_bindings[0]
    selected_template = template_map.get(str(selected_binding["template_id"]))
    return selected_template, binding_details


async def get_template_list() -> list[dict[str, Any]]:
    templates = await SystemDashboardTemplate.filter(is_del=False).order_by("-updated_at", "-created_at").values()
    if not templates:
        return []

    template_ids = [str(item["id"]) for item in templates if item.get("id")]
    bindings = await SystemDashboardRoleTemplate.filter(template_id__in=template_ids, is_del=False).values(
        "template_id", "role_id", "priority"
    )
    role_ids = dedupe_list([str(item["role_id"]) for item in bindings if item.get("role_id")])
    role_rows = await SystemRole.filter(id__in=role_ids, is_del=False).values("id", "name", "code")
    role_map = {str(item["id"]): item for item in role_rows if item.get("id")}

    bindings_map: dict[str, list[dict[str, Any]]] = {}
    for binding in bindings:
        role_item = role_map.get(str(binding["role_id"]), {})
        bindings_map.setdefault(str(binding["template_id"]), []).append(
            {
                "role_id": str(binding["role_id"]),
                "role_name": role_item.get("name") or "",
                "role_code": role_item.get("code") or "",
                "priority": binding.get("priority", 100),
            }
        )

    result = []
    for template in templates:
        template_id = str(template["id"])
        result.append(
            {
                **template,
                "id": template_id,
                "role_bindings": sorted(
                    bindings_map.get(template_id, []),
                    key=lambda item: (item.get("priority", 100), item.get("role_name") or ""),
                ),
            }
        )
    return result


async def sync_role_bindings(template_id: str, role_ids: list[str], priority: int) -> list[str]:
    role_ids = dedupe_list(role_ids)
    if role_ids:
        valid_role_rows = await SystemRole.filter(id__in=role_ids, is_del=False).values_list("id", flat=True)
        valid_role_ids = [str(role_id) for role_id in valid_role_rows if role_id]
    else:
        valid_role_ids = []

    existing_bindings = await SystemDashboardRoleTemplate.filter(template_id=template_id).all()
    for binding in existing_bindings:
        role_id = str(binding.role_id or "")
        if role_id and role_id not in valid_role_ids and not binding.is_del:
            await SystemDashboardRoleTemplate.filter(id=binding.id).update(is_del=True)

    for role_id in valid_role_ids:
        role_bindings = await SystemDashboardRoleTemplate.filter(role_id=role_id).order_by("created_at").all()
        if role_bindings:
            primary = role_bindings[0]
            duplicates = role_bindings[1:]
            for duplicate in duplicates:
                if not duplicate.is_del:
                    await SystemDashboardRoleTemplate.filter(id=duplicate.id).update(is_del=True)
            await SystemDashboardRoleTemplate.filter(id=primary.id).update(
                template_id=template_id,
                priority=priority,
                is_del=False,
            )
        else:
            await SystemDashboardRoleTemplate.create(role_id=role_id, template_id=template_id, priority=priority)

    return valid_role_ids


async def require_dashboard_manager(request: Request) -> tuple[str, dict[str, Any]]:
    payload = getattr(request.state, "user", {}) or {}
    user_id = str(payload.get("sub") or "")
    if not user_id:
        raise PermissionError("未登录或登录已过期")

    access_context = await get_user_access_context(user_id)
    if has_permission_mark(access_context, "dashboard:template:manage") or any(
        is_admin_role(role_code) for role_code in access_context.get("casbin_roles", [])
    ):
        return user_id, access_context

    raise PermissionError("当前账号没有模板管理权限")


@dashboardAPI.get("/workspace")
async def get_workspace(request: Request):
    payload = getattr(request.state, "user", {}) or {}
    user_id = str(payload.get("sub") or "")
    if not user_id:
        return ResponseUtil.unauthorized(msg="未登录或登录已过期")

    user = await SystemUser.filter(id=user_id, is_del=False).first()
    if not user:
        return ResponseUtil.unauthorized(msg="用户不存在或已被禁用")

    access_context = await get_user_access_context(user_id)
    role_template, role_bindings = await get_role_template_for_user(access_context.get("role_ids", []))
    user_config = await SystemDashboardUserConfig.filter(user_id=user_id, is_del=False).first()

    source = "system"
    source_template_id = None
    if user_config and user_config.layout:
        effective_layout = sanitize_layout(user_config.layout, access_context)
        source = "user"
        source_template_id = str(user_config.template_id) if user_config.template_id else None
    elif role_template:
        effective_layout = sanitize_layout(role_template.get("layout"), access_context)
        source = "role"
        source_template_id = str(role_template["id"])
    else:
        effective_layout = sanitize_layout(clone_default_layout(), access_context)

    templates = []
    can_manage_templates = has_permission_mark(access_context, "dashboard:template:manage") or any(
        is_admin_role(role_code) for role_code in access_context.get("casbin_roles", [])
    )
    if can_manage_templates:
        templates = await get_template_list()

    return ResponseUtil.success(
        data={
            "layout": effective_layout,
            "widget_library": get_allowed_widgets(access_context),
            "widget_data": await build_dashboard_metrics(user_id, access_context),
            "personalized": bool(user_config and user_config.layout),
            "source": source,
            "source_template_id": source_template_id,
            "role_template": {
                "id": str(role_template["id"]),
                "name": role_template.get("name"),
                "description": role_template.get("description"),
            }
            if role_template
            else None,
            "role_bindings": role_bindings,
            "permissions": {
                "can_manage_templates": can_manage_templates,
                "has_sensitive_widget": has_permission_mark(access_context, "dashboard:widget:sensitive"),
                "permission_marks": access_context.get("permission_marks", []),
            },
            "templates": templates,
            "user": {"id": str(user.id), "username": user.username, "nickname": user.nickname},
        }
    )


@dashboardAPI.post("/save-layout")
async def save_layout(payload: DashboardLayoutSave, request: Request):
    auth_payload = getattr(request.state, "user", {}) or {}
    user_id = str(auth_payload.get("sub") or "")
    if not user_id:
        return ResponseUtil.unauthorized(msg="未登录或登录已过期")

    access_context = await get_user_access_context(user_id)
    sanitized_layout = sanitize_layout(payload.layout, access_context)
    if not sanitized_layout:
        return ResponseUtil.failure(msg="布局数据不能为空")

    user_config = await SystemDashboardUserConfig.filter(user_id=user_id).first()
    update_payload = {
        "template_id": payload.template_id,
        "layout": sanitized_layout,
        "preferences": payload.preferences or {},
        "is_del": False,
    }

    if user_config:
        await SystemDashboardUserConfig.filter(id=user_config.id).update(**update_payload)
    else:
        await SystemDashboardUserConfig.create(user_id=user_id, **update_payload)

    return ResponseUtil.success(msg="布局已自动保存", data={"layout": sanitized_layout})


@dashboardAPI.post("/reset")
async def reset_layout(request: Request):
    auth_payload = getattr(request.state, "user", {}) or {}
    user_id = str(auth_payload.get("sub") or "")
    if not user_id:
        return ResponseUtil.unauthorized(msg="未登录或登录已过期")

    await SystemDashboardUserConfig.filter(user_id=user_id).update(layout=None, preferences={}, is_del=False)
    return ResponseUtil.success(msg="已恢复为角色默认模板")


@dashboardAPI.get("/templates")
async def list_templates(request: Request):
    try:
        await require_dashboard_manager(request)
    except PermissionError as exc:
        return ResponseUtil.forbidden(msg=str(exc))

    return ResponseUtil.success(data=await get_template_list())


@dashboardAPI.post("/templates")
async def create_template(payload: DashboardTemplateCreate, request: Request):
    try:
        user_id, _ = await require_dashboard_manager(request)
    except PermissionError as exc:
        return ResponseUtil.forbidden(msg=str(exc))

    user = await SystemUser.filter(id=user_id, is_del=False).first()
    template = await SystemDashboardTemplate.create(
        name=payload.name,
        template_key=payload.template_key,
        description=payload.description,
        layout=payload.layout or clone_default_layout(),
        theme_config=payload.theme_config,
        is_public=payload.is_public,
        status=payload.status,
        created_by=user_id,
        created_by_name=(user.nickname or user.username) if user else "",
        updated_by=user_id,
        updated_by_name=(user.nickname or user.username) if user else "",
    )
    role_ids = await sync_role_bindings(str(template.id), payload.role_ids, payload.priority)
    return ResponseUtil.success(msg="模板创建成功", data={"id": str(template.id), "role_ids": role_ids})


@dashboardAPI.put("/templates/{template_id}")
async def update_template(template_id: str, payload: DashboardTemplateUpdate, request: Request):
    try:
        user_id, _ = await require_dashboard_manager(request)
    except PermissionError as exc:
        return ResponseUtil.forbidden(msg=str(exc))

    template = await SystemDashboardTemplate.filter(id=template_id, is_del=False).first()
    if not template:
        return ResponseUtil.failure(msg="模板不存在")

    user = await SystemUser.filter(id=user_id, is_del=False).first()
    update_payload = payload.model_dump(exclude_none=True)
    if "layout" in update_payload:
        update_payload["layout"] = update_payload["layout"] or clone_default_layout()
    update_payload["updated_by"] = user_id
    update_payload["updated_by_name"] = (user.nickname or user.username) if user else ""
    await SystemDashboardTemplate.filter(id=template_id, is_del=False).update(**update_payload)

    role_ids = None
    if payload.role_ids is not None:
        role_ids = await sync_role_bindings(template_id, payload.role_ids, payload.priority or 100)

    return ResponseUtil.success(msg="模板更新成功", data={"id": template_id, "role_ids": role_ids or []})


@dashboardAPI.delete("/templates/{template_id}")
async def delete_template(template_id: str, request: Request):
    try:
        await require_dashboard_manager(request)
    except PermissionError as exc:
        return ResponseUtil.forbidden(msg=str(exc))

    template = await SystemDashboardTemplate.filter(id=template_id, is_del=False).first()
    if not template:
        return ResponseUtil.failure(msg="模板不存在")

    await SystemDashboardTemplate.filter(id=template_id, is_del=False).update(is_del=True)
    await SystemDashboardRoleTemplate.filter(template_id=template_id, is_del=False).update(is_del=True)
    await SystemDashboardUserConfig.filter(template_id=template_id, is_del=False).update(template_id=None)
    return ResponseUtil.success(msg="模板删除成功")
