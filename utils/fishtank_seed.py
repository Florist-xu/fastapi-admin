from __future__ import annotations

from datetime import datetime, timedelta

from models.fishtank import SystemFishTank, SystemFishTankRecord, SystemFishTankSpecies


def build_mock_times(now: datetime) -> dict[str, datetime]:
    last_feed_at = now.replace(hour=7, minute=42, second=0, microsecond=0)
    if last_feed_at > now:
        last_feed_at -= timedelta(days=1)

    last_water_change_at = (now - timedelta(days=8)).replace(hour=18, minute=20, second=0, microsecond=0)
    fish_started_at = (now - timedelta(days=126)).replace(hour=9, minute=0, second=0, microsecond=0)
    last_sync_at = now.replace(second=0, microsecond=0)
    return {
        "fish_started_at": fish_started_at,
        "last_water_change_at": last_water_change_at,
        "last_feed_at": last_feed_at,
        "last_sync_at": last_sync_at,
    }


async def ensure_fishtank_seed_data() -> None:
    now = datetime.now()
    mock_times = build_mock_times(now)

    tank = await SystemFishTank.filter(device_code="tank-livingroom-001").order_by("created_at").first()
    if not tank:
        tank = await SystemFishTank.create(
            name="客厅智能鱼缸",
            device_code="tank-livingroom-001",
            location="客厅靠窗生态位",
            species_name="霓虹灯鱼、孔雀鱼、红鼻剪刀",
            fish_count=12,
            status_source="mock",
            esp32_device_code="esp32-tank-demo-001",
            esp32_last_sync_at=mock_times["last_sync_at"],
            water_temperature=25.8,
            target_temperature=26.0,
            temperature_status="ideal",
            filter_enabled=True,
            filter_mode="循环净化",
            filter_health="running",
            light_enabled=True,
            light_color_name="海湾蓝",
            light_color_hex="#67D4FF",
            fish_started_at=mock_times["fish_started_at"],
            last_water_change_at=mock_times["last_water_change_at"],
            last_feed_at=mock_times["last_feed_at"],
            water_change_cycle_days=7,
            notes="当前设备状态来自数据库模拟，后续可切换到 ESP32 实时数据。",
            last_payload={
                "source": "mock-db",
                "temperature": 25.8,
                "filter_enabled": True,
                "light_enabled": True,
                "light_color_hex": "#67D4FF",
            },
        )

    species_rows = await SystemFishTankSpecies.filter(tank_id=str(tank.id), is_del=False).count()
    if not species_rows:
        await SystemFishTankSpecies.bulk_create(
            [
                SystemFishTankSpecies(
                    tank_id=str(tank.id),
                    species_name="霓虹灯鱼",
                    fish_count=6,
                    display_order=1,
                    notes="中上层活跃，群游效果好。",
                ),
                SystemFishTankSpecies(
                    tank_id=str(tank.id),
                    species_name="孔雀鱼",
                    fish_count=4,
                    display_order=2,
                    notes="尾鳍色彩丰富，适合作为展示主角。",
                ),
                SystemFishTankSpecies(
                    tank_id=str(tank.id),
                    species_name="红鼻剪刀",
                    fish_count=2,
                    display_order=3,
                    notes="有助于提升整体群游层次。",
                ),
            ]
        )

    has_records = await SystemFishTankRecord.filter(tank_id=str(tank.id), is_del=False).exists()
    if has_records:
        return

    records = [
        SystemFishTankRecord(
            tank_id=str(tank.id),
            event_type="water_change",
            title="完成 30% 换水",
            event_time=mock_times["last_water_change_at"],
            note="补充除氯水并重新校准加热棒。",
            operator_name="系统模拟",
            source="mock",
        ),
        SystemFishTankRecord(
            tank_id=str(tank.id),
            event_type="feeding",
            title="上午定时喂食",
            event_time=mock_times["last_feed_at"],
            note="投喂薄片饲料与冻干红虫组合。",
            operator_name="系统模拟",
            source="mock",
        ),
        SystemFishTankRecord(
            tank_id=str(tank.id),
            event_type="light",
            title="灯光切换为海湾蓝",
            event_time=(now - timedelta(days=1)).replace(hour=19, minute=10, second=0, microsecond=0),
            note="进入夜景展示模式，亮度维持 68%。",
            operator_name="系统模拟",
            source="mock",
        ),
        SystemFishTankRecord(
            tank_id=str(tank.id),
            event_type="filter",
            title="过滤系统例行检查",
            event_time=(now - timedelta(days=3)).replace(hour=14, minute=35, second=0, microsecond=0),
            note="确认水流稳定，滤棉状态正常。",
            operator_name="系统模拟",
            source="mock",
        ),
        SystemFishTankRecord(
            tank_id=str(tank.id),
            event_type="feeding",
            title="夜间补充喂食",
            event_time=(now - timedelta(days=2)).replace(hour=20, minute=5, second=0, microsecond=0),
            note="少量颗粒饲料，避免残饵过多。",
            operator_name="系统模拟",
            source="mock",
        ),
        SystemFishTankRecord(
            tank_id=str(tank.id),
            event_type="maintenance",
            title="水质巡检完成",
            event_time=(now - timedelta(days=6)).replace(hour=11, minute=25, second=0, microsecond=0),
            note="透明度与活性状态良好，建议按周期继续换水。",
            operator_name="系统模拟",
            source="mock",
        ),
    ]
    await SystemFishTankRecord.bulk_create(records)
