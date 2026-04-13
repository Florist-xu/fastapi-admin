from tortoise import connections


CREATE_USER_NOTIFICATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `system_user_notification` (
  `id` CHAR(36) NOT NULL DEFAULT (UUID()) PRIMARY KEY COMMENT 'Primary key',
  `is_del` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Soft delete flag',
  `created_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'Created time',
  `updated_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT 'Updated time',
  `notification_id` CHAR(36) NOT NULL COMMENT 'Notification id',
  `user_id` CHAR(36) NULL COMMENT 'User id',
  `is_read` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Read status',
  `read_at` DATETIME(6) NULL COMMENT 'Read time',
  `delivered_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'Delivered time',
  UNIQUE KEY `uk_system_user_notification_unique` (`notification_id`, `user_id`),
  INDEX `idx_system_user_notification_user_id` (`user_id`),
  INDEX `idx_system_user_notification_is_read` (`is_read`),
  CONSTRAINT `fk_system_user_notification_notification` FOREIGN KEY (`notification_id`) REFERENCES `system_notification` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_system_user_notification_user` FOREIGN KEY (`user_id`) REFERENCES `system_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='User notification delivery table'
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


async def ensure_notification_schema() -> None:
    connection = connections.get("default")
    database_name = await fetch_current_database(connection)
    if not database_name:
        return

    existing_tables = await fetch_existing_tables(
        connection,
        database_name,
        ["system_user_notification"],
    )
    if "system_user_notification" not in existing_tables:
        await connection.execute_query(CREATE_USER_NOTIFICATION_TABLE_SQL)
