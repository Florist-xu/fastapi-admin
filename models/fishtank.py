from tortoise import fields

from models.common import BaseModel


class SystemFishTank(BaseModel):
    name = fields.CharField(max_length=120, null=False, description="Fish tank name")
    device_code = fields.CharField(max_length=64, null=False, unique=True, description="Device code")
    location = fields.CharField(max_length=120, null=True, description="Display location")
    species_name = fields.CharField(max_length=120, null=True, description="Fish species name")
    fish_count = fields.IntField(default=0, description="Fish count")
    status_source = fields.CharField(max_length=20, default="mock", description="Data source: mock or esp32")
    esp32_device_code = fields.CharField(max_length=64, null=True, description="ESP32 device code")
    esp32_last_sync_at = fields.DatetimeField(null=True, description="Last ESP32 sync time")
    water_temperature = fields.DecimalField(max_digits=4, decimal_places=1, default=25.0, description="Water temperature")
    target_temperature = fields.DecimalField(max_digits=4, decimal_places=1, null=True, description="Target temperature")
    temperature_status = fields.CharField(max_length=20, default="ideal", description="Temperature status")
    filter_enabled = fields.BooleanField(default=True, description="Whether filter is enabled")
    filter_mode = fields.CharField(max_length=60, default="循环净化", description="Filter mode")
    filter_health = fields.CharField(max_length=20, default="running", description="Filter health state")
    light_enabled = fields.BooleanField(default=True, description="Whether light is enabled")
    light_color_name = fields.CharField(max_length=40, default="海湾蓝", description="Light color name")
    light_color_hex = fields.CharField(max_length=20, default="#67D4FF", description="Light color hex")
    fish_started_at = fields.DatetimeField(null=True, description="Fish keeping start time")
    last_water_change_at = fields.DatetimeField(null=True, description="Last water change time")
    last_feed_at = fields.DatetimeField(null=True, description="Last feeding time")
    water_change_cycle_days = fields.IntField(default=7, description="Recommended water change cycle")
    notes = fields.CharField(max_length=255, null=True, description="Notes")
    last_payload = fields.JSONField(null=True, description="Latest raw device payload")

    class Meta:
        table = "system_fishtank"
        table_description = "Smart fish tank status"
        ordering = ["-updated_at", "-created_at"]


class SystemFishTankRecord(BaseModel):
    tank_id = fields.CharField(max_length=36, null=False, description="Fish tank id")
    event_type = fields.CharField(max_length=32, null=False, description="Record type")
    title = fields.CharField(max_length=120, null=False, description="Record title")
    event_time = fields.DatetimeField(null=False, description="Event time")
    note = fields.CharField(max_length=255, null=True, description="Record note")
    operator_name = fields.CharField(max_length=80, null=True, description="Operator name")
    source = fields.CharField(max_length=20, default="mock", description="Record source")

    class Meta:
        table = "system_fishtank_record"
        table_description = "Smart fish tank event record"
        ordering = ["-event_time", "-created_at"]


class SystemFishTankSpecies(BaseModel):
    tank_id = fields.CharField(max_length=36, null=False, description="Fish tank id")
    species_name = fields.CharField(max_length=120, null=False, description="Fish species name")
    fish_count = fields.IntField(default=0, description="Fish count for this species")
    display_order = fields.IntField(default=0, description="Display order")
    notes = fields.CharField(max_length=255, null=True, description="Species notes")

    class Meta:
        table = "system_fishtank_species"
        table_description = "Smart fish tank species detail"
        ordering = ["display_order", "created_at"]
