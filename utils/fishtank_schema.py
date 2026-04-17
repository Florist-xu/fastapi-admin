from tortoise import connections


CREATE_FISHTANK_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `system_fishtank` (
  `id` CHAR(36) NOT NULL DEFAULT (UUID()) PRIMARY KEY COMMENT 'Primary key',
  `is_del` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Soft delete flag',
  `created_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'Created time',
  `updated_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT 'Updated time',
  `name` VARCHAR(120) NOT NULL COMMENT 'Fish tank name',
  `device_code` VARCHAR(64) NOT NULL COMMENT 'Device code',
  `location` VARCHAR(120) NULL COMMENT 'Display location',
  `species_name` VARCHAR(120) NULL COMMENT 'Fish species name',
  `fish_count` INT NOT NULL DEFAULT 0 COMMENT 'Fish count',
  `status_source` VARCHAR(20) NOT NULL DEFAULT 'mock' COMMENT 'Data source',
  `esp32_device_code` VARCHAR(64) NULL COMMENT 'ESP32 device code',
  `esp32_last_sync_at` DATETIME(6) NULL COMMENT 'Last ESP32 sync time',
  `water_temperature` DECIMAL(4,1) NOT NULL DEFAULT 25.0 COMMENT 'Water temperature',
  `target_temperature` DECIMAL(4,1) NULL COMMENT 'Target temperature',
  `temperature_status` VARCHAR(20) NOT NULL DEFAULT 'ideal' COMMENT 'Temperature status',
  `filter_enabled` TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'Whether filter is enabled',
  `filter_mode` VARCHAR(60) NOT NULL DEFAULT '循环净化' COMMENT 'Filter mode',
  `filter_health` VARCHAR(20) NOT NULL DEFAULT 'running' COMMENT 'Filter health state',
  `light_enabled` TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'Whether light is enabled',
  `light_color_name` VARCHAR(40) NOT NULL DEFAULT '海湾蓝' COMMENT 'Light color name',
  `light_color_hex` VARCHAR(20) NOT NULL DEFAULT '#67D4FF' COMMENT 'Light color hex',
  `fish_started_at` DATETIME(6) NULL COMMENT 'Fish keeping start time',
  `last_water_change_at` DATETIME(6) NULL COMMENT 'Last water change time',
  `last_feed_at` DATETIME(6) NULL COMMENT 'Last feeding time',
  `water_change_cycle_days` INT NOT NULL DEFAULT 7 COMMENT 'Recommended water change cycle',
  `notes` VARCHAR(255) NULL COMMENT 'Notes',
  `last_payload` JSON NULL COMMENT 'Latest raw device payload',
  UNIQUE KEY `uk_system_fishtank_device_code` (`device_code`),
  INDEX `idx_system_fishtank_status_source` (`status_source`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Smart fish tank status table'
"""


CREATE_FISHTANK_RECORD_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `system_fishtank_record` (
  `id` CHAR(36) NOT NULL DEFAULT (UUID()) PRIMARY KEY COMMENT 'Primary key',
  `is_del` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Soft delete flag',
  `created_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'Created time',
  `updated_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT 'Updated time',
  `tank_id` CHAR(36) NOT NULL COMMENT 'Fish tank id',
  `event_type` VARCHAR(32) NOT NULL COMMENT 'Record type',
  `title` VARCHAR(120) NOT NULL COMMENT 'Record title',
  `event_time` DATETIME(6) NOT NULL COMMENT 'Event time',
  `note` VARCHAR(255) NULL COMMENT 'Record note',
  `operator_name` VARCHAR(80) NULL COMMENT 'Operator name',
  `source` VARCHAR(20) NOT NULL DEFAULT 'mock' COMMENT 'Record source',
  INDEX `idx_system_fishtank_record_tank_id` (`tank_id`),
  INDEX `idx_system_fishtank_record_event_time` (`event_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Smart fish tank record table'
"""


CREATE_FISHTANK_SPECIES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `system_fishtank_species` (
  `id` CHAR(36) NOT NULL DEFAULT (UUID()) PRIMARY KEY COMMENT 'Primary key',
  `is_del` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Soft delete flag',
  `created_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'Created time',
  `updated_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT 'Updated time',
  `tank_id` CHAR(36) NOT NULL COMMENT 'Fish tank id',
  `species_name` VARCHAR(120) NOT NULL COMMENT 'Fish species name',
  `fish_count` INT NOT NULL DEFAULT 0 COMMENT 'Fish count for this species',
  `display_order` INT NOT NULL DEFAULT 0 COMMENT 'Display order',
  `notes` VARCHAR(255) NULL COMMENT 'Species notes',
  INDEX `idx_system_fishtank_species_tank_id` (`tank_id`),
  INDEX `idx_system_fishtank_species_order` (`display_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Smart fish tank species detail table'
"""


async def fetch_current_database(connection) -> str:
    rows = await connection.execute_query_dict("SELECT DATABASE() AS db_name")
    if not rows:
        return ""
    return rows[0].get("db_name") or ""


async def fetch_existing_tables(connection, database_name: str, table_names: list[str]) -> set[str]:
    if not table_names:
        return set()

    placeholders = ", ".join(["%s"] * len(table_names))
    rows = await connection.execute_query_dict(
        f"""
        SELECT TABLE_NAME
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({placeholders})
        """,
        [database_name, *table_names],
    )
    return {row["TABLE_NAME"] for row in rows}


async def fetch_existing_columns(connection, database_name: str, table_name: str) -> set[str]:
    rows = await connection.execute_query_dict(
        """
        SELECT COLUMN_NAME
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """,
        [database_name, table_name],
    )
    return {row["COLUMN_NAME"] for row in rows}


async def ensure_fishtank_schema() -> None:
    connection = connections.get("default")
    database_name = await fetch_current_database(connection)
    if not database_name:
        return

    table_names = ["system_fishtank", "system_fishtank_record", "system_fishtank_species"]
    existing_tables = await fetch_existing_tables(connection, database_name, table_names)

    if "system_fishtank" not in existing_tables:
        await connection.execute_query(CREATE_FISHTANK_TABLE_SQL)
    else:
        fishtank_columns = await fetch_existing_columns(connection, database_name, "system_fishtank")
        if "species_name" not in fishtank_columns:
            await connection.execute_query(
                "ALTER TABLE `system_fishtank` ADD COLUMN `species_name` VARCHAR(120) NULL COMMENT 'Fish species name'"
            )
        if "fish_count" not in fishtank_columns:
            await connection.execute_query(
                "ALTER TABLE `system_fishtank` ADD COLUMN `fish_count` INT NOT NULL DEFAULT 0 COMMENT 'Fish count'"
            )
    if "system_fishtank_record" not in existing_tables:
        await connection.execute_query(CREATE_FISHTANK_RECORD_TABLE_SQL)
    if "system_fishtank_species" not in existing_tables:
        await connection.execute_query(CREATE_FISHTANK_SPECIES_TABLE_SQL)
