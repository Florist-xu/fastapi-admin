from tortoise import connections


CREATE_SCHEDULED_ACTION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `system_scheduled_action` (
  `id` CHAR(36) NOT NULL DEFAULT (UUID()) PRIMARY KEY COMMENT 'Primary key',
  `is_del` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Soft delete flag',
  `created_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'Created time',
  `updated_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT 'Updated time',
  `actor_id` CHAR(36) NULL COMMENT 'Scheduler user id',
  `actor_name` VARCHAR(255) NULL COMMENT 'Scheduler user name',
  `operation_type` VARCHAR(80) NOT NULL COMMENT 'Normalized operation type',
  `resource` VARCHAR(40) NOT NULL COMMENT 'Resource group',
  `action` VARCHAR(40) NOT NULL COMMENT 'Action name',
  `summary` VARCHAR(500) NULL COMMENT 'Task summary',
  `payload` JSON NULL COMMENT 'Normalized execution payload',
  `execute_at` DATETIME(6) NOT NULL COMMENT 'Execute at',
  `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/running/succeeded/failed',
  `started_at` DATETIME(6) NULL COMMENT 'Started time',
  `executed_at` DATETIME(6) NULL COMMENT 'Executed time',
  `result_message` TEXT NULL COMMENT 'Result message',
  `error_message` TEXT NULL COMMENT 'Error message',
  INDEX `idx_system_scheduled_action_execute_at` (`execute_at`),
  INDEX `idx_system_scheduled_action_status` (`status`),
  INDEX `idx_system_scheduled_action_actor_id` (`actor_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Scheduled action task'
"""


CREATE_SCHEDULED_CLIENT_EVENT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `system_scheduled_client_event` (
  `id` CHAR(36) NOT NULL DEFAULT (UUID()) PRIMARY KEY COMMENT 'Primary key',
  `is_del` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Soft delete flag',
  `created_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'Created time',
  `updated_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT 'Updated time',
  `user_id` CHAR(36) NOT NULL COMMENT 'Target user id',
  `action_name` VARCHAR(50) NOT NULL COMMENT 'Client action name',
  `summary` VARCHAR(255) NULL COMMENT 'Client action summary',
  `payload` JSON NULL COMMENT 'Client action payload',
  `source_task_id` CHAR(36) NULL COMMENT 'Source task id',
  `available_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'Available time',
  `consumed_at` DATETIME(6) NULL COMMENT 'Consumed time',
  INDEX `idx_system_scheduled_client_event_user_id` (`user_id`),
  INDEX `idx_system_scheduled_client_event_available_at` (`available_at`),
  INDEX `idx_system_scheduled_client_event_consumed_at` (`consumed_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Scheduled client event queue'
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


async def ensure_scheduled_action_schema() -> None:
    connection = connections.get("default")
    database_name = await fetch_current_database(connection)
    if not database_name:
        return

    table_names = [
        "system_scheduled_action",
        "system_scheduled_client_event",
    ]
    existing_tables = await fetch_existing_tables(connection, database_name, table_names)

    if "system_scheduled_action" not in existing_tables:
        await connection.execute_query(CREATE_SCHEDULED_ACTION_TABLE_SQL)
    if "system_scheduled_client_event" not in existing_tables:
        await connection.execute_query(CREATE_SCHEDULED_CLIENT_EVENT_TABLE_SQL)
