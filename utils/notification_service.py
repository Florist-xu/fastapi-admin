from __future__ import annotations

import ipaddress
import json
import os
from datetime import datetime
from typing import Iterable

import httpx
from fastapi import Request

from models.notification import SystemNotification, SystemUserNotification
from models.operation_log import SystemOperationLog
from models.user import SystemUser

TYPE_MAP = {
    "notice": 0,
    "announcement": 1,
    "message": 2,
}
LOGIN_OPERATION_NAME = "login_record"


def get_request_ip(request: Request) -> str:
    forwarded_for = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip

    return getattr(request.client, "host", "") or "未知 IP"


def parse_browser_name(user_agent: str) -> str:
    ua = user_agent.lower()
    if "edg/" in ua:
        return "Microsoft Edge"
    if "chrome/" in ua and "edg/" not in ua:
        return "Google Chrome"
    if "firefox/" in ua:
        return "Mozilla Firefox"
    if "safari/" in ua and "chrome/" not in ua:
        return "Safari"
    if "opr/" in ua or "opera/" in ua:
        return "Opera"
    if "micromessenger/" in ua:
        return "微信"
    return "未知浏览器"


def parse_os_name(user_agent: str) -> str:
    ua = user_agent.lower()
    if "windows nt 10.0" in ua:
        return "Windows 10/11"
    if "windows nt 6.3" in ua:
        return "Windows 8.1"
    if "windows nt 6.1" in ua:
        return "Windows 7"
    if "iphone" in ua or "ipad" in ua or "ios" in ua:
        return "iOS"
    if "android" in ua:
        return "Android"
    if "mac os x" in ua or "macintosh" in ua:
        return "macOS"
    if "linux" in ua:
        return "Linux"
    return "未知系统"


def is_private_ip(ip_address: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_address)
    except ValueError:
        return False
    return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved


async def resolve_ip_location(ip_address: str) -> str:
    if not ip_address or ip_address == "未知 IP":
        return "未知地点"

    if is_private_ip(ip_address):
        return "本机或内网"

    api_url = os.getenv("IP_LOCATION_API_URL", "https://ipwho.is/{ip}").strip()
    url = api_url.replace("{ip}", ip_address)

    try:
        timeout = httpx.Timeout(5.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers={"Accept": "application/json"})
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return "未知地点"

    if isinstance(payload, dict) and payload.get("success") is False:
        return "未知地点"

    country = str(payload.get("country") or payload.get("country_name") or "").strip()
    region = str(payload.get("region") or payload.get("regionName") or "").strip()
    city = str(payload.get("city") or "").strip()
    isp = str(payload.get("connection", {}).get("isp") or payload.get("isp") or "").strip()

    location_parts = [item for item in [country, region, city] if item]
    location = " / ".join(location_parts) if location_parts else "未知地点"
    return f"{location} ({isp})" if isp else location


async def create_login_operation_log(
    user: SystemUser,
    request: Request,
    ip_address: str,
    location: str,
    browser_name: str,
    os_name: str,
    user_agent: str,
) -> SystemOperationLog:
    return await SystemOperationLog.create(
        operation_name=LOGIN_OPERATION_NAME,
        operation_type=1,
        request_path=request.url.path,
        request_method=request.method,
        host=ip_address,
        location=location,
        user_agent=user_agent,
        browser=browser_name,
        os=os_name,
        request_params=json.dumps(
            {"username": user.username, "nickname": user.nickname or "", "login": True},
            ensure_ascii=False,
        ),
        response_result=json.dumps({"message": "login success"}, ensure_ascii=False),
        status=1,
        cost_time=0,
        operator_id=str(user.id),
    )


async def list_recent_login_logs(user_id: str, limit: int = 5) -> list[SystemOperationLog]:
    return await SystemOperationLog.filter(
        is_del=False,
        operation_name=LOGIN_OPERATION_NAME,
        operator_id=user_id,
        status=1,
    ).order_by("-created_at").limit(limit)


def build_login_anomaly_summary(
    current_ip: str,
    current_browser: str,
    current_os: str,
    current_location: str,
    previous_log: SystemOperationLog | None,
) -> str:
    if previous_log is None:
        return "首次登录记录，暂无历史对比。"

    issues: list[str] = []
    if (previous_log.host or "") != current_ip:
        issues.append(f"IP 发生变化：{previous_log.host or '未知'} -> {current_ip}")
    if (previous_log.browser or "") != current_browser:
        issues.append(f"浏览器发生变化：{previous_log.browser or '未知'} -> {current_browser}")
    if (previous_log.os or "") != current_os:
        issues.append(f"操作系统发生变化：{previous_log.os or '未知'} -> {current_os}")
    if (previous_log.location or "") not in ("", "未知地点") and previous_log.location != current_location:
        issues.append(f"登录地点发生变化：{previous_log.location} -> {current_location}")

    if not issues:
        return "未发现异常，本次登录环境与最近一次记录一致。"

    return "检测到登录环境变化：" + "；".join(issues)


def build_recent_login_history(logs: list[SystemOperationLog]) -> str:
    if not logs:
        return "<p>暂无历史登录记录。</p>"

    items = []
    for log in logs:
        login_time = (log.created_at or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
        items.append(
            "<li>"
            f"{login_time} | IP：{log.host or '未知'} | 地点：{log.location or '未知地点'} | "
            f"浏览器：{log.browser or '未知'} | 系统：{log.os or '未知'}"
            "</li>"
        )
    return "<ol>" + "".join(items) + "</ol>"


def build_login_notification_content(
    display_name: str,
    login_time: datetime,
    ip_address: str,
    browser_name: str,
    os_name: str,
    user_agent: str,
    location: str,
    anomaly_summary: str,
    recent_history_html: str,
) -> str:
    return "\n".join(
        [
            f"<p>用户 <strong>{display_name}</strong> 于 {login_time.strftime('%Y-%m-%d %H:%M:%S')} 登录系统。</p>",
            f"<p>登录 IP：{ip_address}</p>",
            f"<p>登录地点：{location}</p>",
            f"<p>浏览器：{browser_name}</p>",
            f"<p>操作系统：{os_name}</p>",
            f"<p>异常提醒：{anomaly_summary}</p>",
            "<p>最近连续登录记录：</p>",
            recent_history_html,
            f"<p>User-Agent：{user_agent or '未知'}</p>",
        ]
    )


def normalize_string_list(values: Iterable[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        normalized = str(value).strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def normalize_int_list(values: Iterable[int] | None) -> list[int]:
    result: list[int] = []
    for value in values or []:
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            continue
        if normalized not in result:
            result.append(normalized)
    return result


async def resolve_notification_user_ids(notification: SystemNotification) -> list[str]:
    if notification.scope == 0:
        rows = await SystemUser.filter(is_del=False, status=1).values_list("id", flat=True)
        return normalize_string_list(rows)

    scope_ids = normalize_string_list(notification.scope_ids)
    if not scope_ids:
        return []

    if notification.scope == 1:
        rows = await SystemUser.filter(
            is_del=False,
            status=1,
            department_id__in=scope_ids,
        ).values_list("id", flat=True)
        return normalize_string_list(rows)

    target_user_ids = [item for item in scope_ids if not item.startswith("user_type:")]
    target_user_types = normalize_int_list(
        item.split(":", 1)[1] for item in scope_ids if item.startswith("user_type:")
    )

    user_ids: list[str] = []
    if target_user_ids:
        rows = await SystemUser.filter(is_del=False, status=1, id__in=target_user_ids).values_list("id", flat=True)
        user_ids.extend(normalize_string_list(rows))

    if target_user_types:
        rows = await SystemUser.filter(is_del=False, status=1, user_type__in=target_user_types).values_list(
            "id", flat=True
        )
        user_ids.extend(normalize_string_list(rows))

    return normalize_string_list(user_ids)


async def publish_notification(
    notification: SystemNotification,
    actor_id: str | None = None,
    actor_name: str | None = None,
) -> int:
    user_ids = await resolve_notification_user_ids(notification)
    if not user_ids:
        return 0

    now = datetime.now()
    await SystemNotification.filter(id=notification.id).update(
        status=1,
        publish_time=now,
    )

    existing_user_ids = normalize_string_list(
        await SystemUserNotification.filter(
            notification_id=notification.id,
            user_id__in=user_ids,
        ).values_list("user_id", flat=True)
    )

    new_deliveries = [
        SystemUserNotification(notification_id=notification.id, user_id=user_id, delivered_at=now)
        for user_id in user_ids
        if user_id not in existing_user_ids
    ]
    if new_deliveries:
        await SystemUserNotification.bulk_create(new_deliveries)

    return len(user_ids)


async def create_login_notification(user: SystemUser, request: Request) -> None:
    now = datetime.now()
    display_name = user.nickname or user.username
    user_agent = (request.headers.get("user-agent") or "").strip()
    ip_address = get_request_ip(request)
    browser_name = parse_browser_name(user_agent)
    os_name = parse_os_name(user_agent)
    location = await resolve_ip_location(ip_address)

    await create_login_operation_log(
        user=user,
        request=request,
        ip_address=ip_address,
        location=location,
        browser_name=browser_name,
        os_name=os_name,
        user_agent=user_agent,
    )

    recent_logs = await list_recent_login_logs(str(user.id), limit=5)
    previous_log = recent_logs[1] if len(recent_logs) > 1 else None
    anomaly_summary = build_login_anomaly_summary(
        current_ip=ip_address,
        current_browser=browser_name,
        current_os=os_name,
        current_location=location,
        previous_log=previous_log,
    )
    recent_history_html = build_recent_login_history(recent_logs)

    title = "登录提醒"
    content = build_login_notification_content(
        display_name=display_name,
        login_time=now,
        ip_address=ip_address,
        browser_name=browser_name,
        os_name=os_name,
        user_agent=user_agent,
        location=location,
        anomaly_summary=anomaly_summary,
        recent_history_html=recent_history_html,
    )

    notification = await SystemNotification.create(
        title=title,
        content=content,
        type=TYPE_MAP["notice"],
        scope=2,
        scope_ids=[str(user.id)],
        priority=1,
        status=1,
        publish_time=now,
        creator_id=str(user.id),
    )
    await SystemUserNotification.create(
        notification_id=notification.id,
        user_id=user.id,
        delivered_at=now,
    )
