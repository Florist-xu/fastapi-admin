from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from models.fishtank import SystemFishTank, SystemFishTankRecord, SystemFishTankSpecies
from utils.response import ResponseUtil


fishtankAPI = APIRouter(prefix="/fishtank", tags=["fishtank"])

EVENT_LABELS = {
    "water_change": ("换水", "cyan"),
    "feeding": ("喂食", "emerald"),
    "light": ("灯光", "violet"),
    "filter": ("过滤", "amber"),
    "maintenance": ("巡检", "cyan"),
}

LIGHT_COLOR_MAP = {
    "海湾蓝": "#67D4FF",
    "珊瑚橙": "#FFAA6C",
    "森林青": "#58D5B5",
    "月光白": "#E8F6FF",
    "暮光紫": "#A78BFA",
}


class FishTankSpeciesPayload(BaseModel):
    species_name: str = Field(..., min_length=1, max_length=120)
    fish_count: int = Field(default=0, ge=0, le=9999)
    notes: str | None = Field(default=None, max_length=255)


class FishTankSimulationPayload(BaseModel):
    device_code: str | None = None
    water_temperature: float | None = Field(default=None, ge=18, le=35)
    target_temperature: float | None = Field(default=None, ge=18, le=35)
    filter_enabled: bool | None = None
    light_enabled: bool | None = None
    light_color_name: str | None = Field(default=None, max_length=40)
    light_color_hex: str | None = Field(default=None, max_length=20)
    fish_keeping_days: int | None = Field(default=None, ge=0, le=9999)
    fish_started_at: datetime | None = None
    fish_count: int | None = Field(default=None, ge=0, le=9999)
    species_items: list[FishTankSpeciesPayload] | None = None
    action: Literal["feed", "water_change"] | None = None


def to_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def days_between(start_at: datetime | None, end_at: datetime) -> int:
    if start_at is None:
        return 0
    return max((end_at.date() - start_at.date()).days, 0)


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return "--"
    return value.strftime("%Y-%m-%d %H:%M")


def format_time(value: datetime | None) -> str:
    if value is None:
        return "--:--"
    return value.strftime("%H:%M")


def infer_temperature_status(temperature: float | None) -> str:
    if temperature is None:
        return "warning"
    if 24.0 <= temperature <= 27.0:
        return "ideal"
    if 23.0 <= temperature < 24.0 or 27.0 < temperature <= 28.0:
        return "attention"
    return "warning"


def build_temperature_label(temperature: float | None) -> tuple[str, str]:
    status = infer_temperature_status(temperature)
    if temperature is None:
        return "暂无温度数据", status
    if status == "ideal":
        return "水温稳定，适合观赏鱼日常活动。", status
    if status == "attention":
        return "水温轻微波动，建议留意加热棒或环境温差。", status
    return "水温偏离舒适区，建议尽快调整。", status


def build_care_tip(days_since_water_change: int, water_change_cycle_days: int, filter_enabled: bool) -> str:
    if not filter_enabled:
        return "过滤已关闭，建议先恢复过滤再观察水质变化。"
    if days_since_water_change >= water_change_cycle_days:
        return "已经到换水周期，建议今天安排一次局部换水。"
    if days_since_water_change >= max(water_change_cycle_days - 2, 1):
        return "距离建议换水周期不远，可以提前准备新水。"
    return "当前养护节奏良好，维持现有巡检频率即可。"


def serialize_record(record: dict[str, Any]) -> dict[str, Any]:
    event_type = record.get("event_type")
    event_type_value = event_type if isinstance(event_type, str) else "record"
    badge, tone = EVENT_LABELS.get(event_type_value, ("记录", "cyan"))
    return {
        "id": str(record.get("id")),
        "event_type": event_type_value,
        "title": record.get("title") or "鱼缸动态",
        "event_time": record.get("event_time"),
        "note": record.get("note") or "",
        "operator_name": record.get("operator_name") or "",
        "badge": badge,
        "tone": tone,
    }


def serialize_species_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id")),
        "species_name": item.get("species_name") or "",
        "fish_count": int(item.get("fish_count") or 0),
        "notes": item.get("notes") or "",
        "display_order": int(item.get("display_order") or 0),
    }


def normalize_species_items(items: list[FishTankSpeciesPayload] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items or []:
        species_name = item.species_name.strip()
        if not species_name:
            continue
        normalized.append(
            {
                "species_name": species_name,
                "fish_count": int(item.fish_count),
                "notes": (item.notes or "").strip() or None,
            }
        )
    return normalized


def build_species_summary(items: list[dict[str, Any]]) -> str:
    species_names = [item["species_name"] for item in items if item.get("species_name")]
    return "、".join(species_names)


async def fetch_target_tank(device_code: str | None = None) -> SystemFishTank | None:
    query = SystemFishTank.filter(is_del=False)
    if device_code:
        query = query.filter(device_code=device_code)
    return await query.order_by("-updated_at", "-created_at").first()


async def fetch_recent_records(tank_id: str) -> list[dict]:
    records = await (
        SystemFishTankRecord.filter(tank_id=tank_id, is_del=False)
        .order_by("-event_time", "-created_at")
        .limit(8)
        .values("id", "event_type", "title", "event_time", "note", "operator_name")
    )
    return [serialize_record(record) for record in records]


async def fetch_species_items(tank_id: str) -> list[dict]:
    rows = await (
        SystemFishTankSpecies.filter(tank_id=tank_id, is_del=False)
        .order_by("display_order", "created_at")
        .values("id", "species_name", "fish_count", "notes", "display_order")
    )
    return [serialize_species_item(row) for row in rows]


async def build_dashboard_payload(tank: SystemFishTank) -> dict:
    now = datetime.now()
    water_temperature = to_float(tank.water_temperature)
    target_temperature = to_float(tank.target_temperature)
    fish_keeping_days = days_between(tank.fish_started_at, now)
    days_since_water_change = days_between(tank.last_water_change_at, now)
    temperature_label, temperature_status = build_temperature_label(water_temperature)
    species_items = await fetch_species_items(str(tank.id))
    species_summary = build_species_summary(species_items) or (tank.species_name or "")
    total_fish_count = sum(item["fish_count"] for item in species_items) if species_items else int(tank.fish_count or 0)

    return {
        "tank": {
            "id": str(tank.id),
            "name": tank.name,
            "device_code": tank.device_code,
            "location": tank.location,
            "species_name": species_summary,
            "fish_count": total_fish_count,
            "species_items": species_items,
            "status_source": tank.status_source,
            "esp32_device_code": tank.esp32_device_code,
            "esp32_last_sync_at": tank.esp32_last_sync_at,
            "water_temperature": water_temperature,
            "target_temperature": target_temperature,
            "temperature_status": tank.temperature_status or temperature_status,
            "temperature_label": temperature_label,
            "filter_enabled": bool(tank.filter_enabled),
            "filter_mode": tank.filter_mode,
            "filter_health": tank.filter_health,
            "light_enabled": bool(tank.light_enabled),
            "light_color_name": tank.light_color_name,
            "light_color_hex": tank.light_color_hex,
            "fish_keeping_days": fish_keeping_days,
            "fish_started_at": tank.fish_started_at,
            "last_water_change_at": tank.last_water_change_at,
            "last_water_change_text": format_datetime(tank.last_water_change_at),
            "days_since_water_change": days_since_water_change,
            "last_feed_at": tank.last_feed_at,
            "last_feed_time_text": format_time(tank.last_feed_at),
            "water_change_cycle_days": tank.water_change_cycle_days,
            "care_tip": build_care_tip(
                days_since_water_change,
                int(tank.water_change_cycle_days or 7),
                bool(tank.filter_enabled),
            ),
            "notes": tank.notes,
        },
        "records": await fetch_recent_records(str(tank.id)),
    }


async def append_record(
    tank_id: str,
    event_type: str,
    title: str,
    note: str,
    event_time: datetime | None = None,
    operator_name: str = "模拟面板",
) -> None:
    await SystemFishTankRecord.create(
        tank_id=tank_id,
        event_type=event_type,
        title=title,
        event_time=event_time or datetime.now(),
        note=note,
        operator_name=operator_name,
        source="mock",
    )


async def replace_species_items(tank_id: str, items: list[dict]) -> None:
    await SystemFishTankSpecies.filter(tank_id=tank_id, is_del=False).update(is_del=True)
    if not items:
        return

    await SystemFishTankSpecies.bulk_create(
        [
            SystemFishTankSpecies(
                tank_id=tank_id,
                species_name=item["species_name"],
                fish_count=item["fish_count"],
                notes=item.get("notes"),
                display_order=index + 1,
            )
            for index, item in enumerate(items)
        ]
    )


@fishtankAPI.get("/dashboard", summary="智能鱼缸概览")
async def get_fishtank_dashboard(device_code: str | None = Query(default=None)):
    tank = await fetch_target_tank(device_code)
    if not tank:
        return ResponseUtil.failure(msg="未找到鱼缸设备数据")

    return ResponseUtil.success(data=await build_dashboard_payload(tank))


@fishtankAPI.put("/simulate", summary="更新鱼缸模拟状态")
async def update_fishtank_simulation(payload: FishTankSimulationPayload):
    tank = await fetch_target_tank(payload.device_code)
    if not tank:
        return ResponseUtil.failure(msg="未找到鱼缸设备数据")

    now = datetime.now()
    update_payload: dict = {
        "status_source": "mock",
    }

    next_water_temperature = payload.water_temperature if payload.water_temperature is not None else to_float(tank.water_temperature)
    next_target_temperature = payload.target_temperature if payload.target_temperature is not None else to_float(tank.target_temperature)
    next_filter_enabled = bool(payload.filter_enabled) if payload.filter_enabled is not None else bool(tank.filter_enabled)
    next_light_enabled = bool(payload.light_enabled) if payload.light_enabled is not None else bool(tank.light_enabled)
    next_light_color_name = payload.light_color_name or tank.light_color_name
    next_light_color_hex = payload.light_color_hex or LIGHT_COLOR_MAP.get(next_light_color_name, tank.light_color_hex)
    next_fish_started_at = payload.fish_started_at or tank.fish_started_at
    next_fish_keeping_days = (
        days_between(next_fish_started_at, now)
        if payload.fish_started_at is not None
        else payload.fish_keeping_days if payload.fish_keeping_days is not None else days_between(tank.fish_started_at, now)
    )
    normalized_species_items = normalize_species_items(payload.species_items)

    if payload.water_temperature is not None:
        update_payload["water_temperature"] = round(payload.water_temperature, 1)
    if payload.target_temperature is not None:
        update_payload["target_temperature"] = round(payload.target_temperature, 1)

    update_payload["temperature_status"] = infer_temperature_status(next_water_temperature)

    if payload.filter_enabled is not None and payload.filter_enabled != bool(tank.filter_enabled):
        update_payload["filter_enabled"] = payload.filter_enabled
        update_payload["filter_health"] = "running" if payload.filter_enabled else "paused"
        await append_record(
            str(tank.id),
            "filter",
            f"过滤系统已{'开启' if payload.filter_enabled else '关闭'}",
            "状态已通过页面模拟控制台修改。",
            event_time=now,
        )

    if payload.light_enabled is not None and payload.light_enabled != bool(tank.light_enabled):
        update_payload["light_enabled"] = payload.light_enabled
        await append_record(
            str(tank.id),
            "light",
            f"灯光已{'开启' if payload.light_enabled else '关闭'}",
            "灯光开关已通过页面模拟控制台更新。",
            event_time=now,
        )

    if payload.light_color_name is not None or payload.light_color_hex is not None:
        update_payload["light_color_name"] = next_light_color_name
        update_payload["light_color_hex"] = next_light_color_hex
        if next_light_enabled:
            await append_record(
                str(tank.id),
                "light",
                f"灯光切换为{next_light_color_name}",
                f"当前颜色值为 {next_light_color_hex}。",
                event_time=now,
            )

    if payload.fish_started_at is not None:
        update_payload["fish_started_at"] = payload.fish_started_at
        await append_record(
            str(tank.id),
            "maintenance",
            f"养鱼开始日期更新为 {payload.fish_started_at.strftime('%Y-%m-%d')}",
            "系统已根据开始日期自动重新计算养鱼天数。",
            event_time=now,
        )
    elif payload.fish_keeping_days is not None:
        update_payload["fish_started_at"] = now - timedelta(days=payload.fish_keeping_days)
        await append_record(
            str(tank.id),
            "maintenance",
            f"养鱼记录更新为 {payload.fish_keeping_days} 天",
            "建缸起始时间已按最新模拟值重新换算。",
            event_time=now,
        )

    if payload.species_items is not None:
        total_fish_count = sum(item["fish_count"] for item in normalized_species_items)
        species_summary = build_species_summary(normalized_species_items)
        update_payload["fish_count"] = total_fish_count
        update_payload["species_name"] = species_summary or "未设置品种"
        await replace_species_items(str(tank.id), normalized_species_items)
        await append_record(
            str(tank.id),
            "maintenance",
            "鱼群配置已更新",
            f"当前共 {total_fish_count} 条，包含 {species_summary or '未设置品种'}。",
            event_time=now,
        )
    elif payload.fish_count is not None:
        update_payload["fish_count"] = payload.fish_count
        await append_record(
            str(tank.id),
            "maintenance",
            f"鱼只数量已调整为 {payload.fish_count} 条",
            "总数量已通过模拟控制台手动更新。",
            event_time=now,
        )

    if payload.action == "feed":
        update_payload["last_feed_at"] = now
        await append_record(
            str(tank.id),
            "feeding",
            "记录一次喂食",
            "已通过模拟控制台记录本次喂食时间。",
            event_time=now,
        )
    elif payload.action == "water_change":
        update_payload["last_water_change_at"] = now
        await append_record(
            str(tank.id),
            "water_change",
            "完成一次换水",
            "已通过模拟控制台记录本次换水时间。",
            event_time=now,
        )

    update_payload["last_payload"] = {
        "source": "mock-panel",
        "water_temperature": next_water_temperature,
        "target_temperature": next_target_temperature,
        "filter_enabled": next_filter_enabled,
        "light_enabled": next_light_enabled,
        "light_color_name": next_light_color_name,
        "light_color_hex": next_light_color_hex,
        "fish_keeping_days": next_fish_keeping_days,
        "fish_started_at": next_fish_started_at.isoformat() if next_fish_started_at else None,
        "species_items": normalized_species_items if payload.species_items is not None else None,
        "action": payload.action,
        "updated_at": now.isoformat(),
    }

    await SystemFishTank.filter(id=tank.id, is_del=False).update(**update_payload)
    refreshed_tank = await SystemFishTank.get(id=tank.id)
    return ResponseUtil.success(msg="鱼缸模拟状态已更新", data=await build_dashboard_payload(refreshed_tank))
