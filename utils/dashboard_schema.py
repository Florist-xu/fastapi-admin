from tortoise import connections


CREATE_DASHBOARD_TEMPLATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `system_dashboard_template` (
  `id` CHAR(36) NOT NULL DEFAULT (UUID()) PRIMARY KEY COMMENT 'Primary key',
  `is_del` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Soft delete flag',
  `created_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'Created time',
  `updated_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT 'Updated time',
  `name` VARCHAR(120) NOT NULL COMMENT 'Template name',
  `template_key` VARCHAR(120) NULL COMMENT 'Template key',
  `description` VARCHAR(500) NULL COMMENT 'Template description',
  `layout` JSON NOT NULL COMMENT 'Dashboard layout schema',
  `theme_config` JSON NULL COMMENT 'Theme config',
  `is_public` TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'Whether template is public',
  `status` SMALLINT NOT NULL DEFAULT 1 COMMENT 'Template status',
  `created_by` CHAR(36) NULL COMMENT 'Creator user id',
  `created_by_name` VARCHAR(255) NULL COMMENT 'Creator display name',
  `updated_by` CHAR(36) NULL COMMENT 'Last updater user id',
  `updated_by_name` VARCHAR(255) NULL COMMENT 'Last updater display name',
  INDEX `idx_system_dashboard_template_status` (`status`),
  INDEX `idx_system_dashboard_template_public` (`is_public`),
  INDEX `idx_system_dashboard_template_key` (`template_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Dashboard template table'
"""


CREATE_DASHBOARD_ROLE_TEMPLATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `system_dashboard_role_template` (
  `id` CHAR(36) NOT NULL DEFAULT (UUID()) PRIMARY KEY COMMENT 'Primary key',
  `is_del` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Soft delete flag',
  `created_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'Created time',
  `updated_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT 'Updated time',
  `role_id` CHAR(36) NOT NULL COMMENT 'Role id',
  `template_id` CHAR(36) NOT NULL COMMENT 'Template id',
  `priority` INT NOT NULL DEFAULT 100 COMMENT 'Binding priority',
  INDEX `idx_system_dashboard_role_template_role` (`role_id`),
  INDEX `idx_system_dashboard_role_template_template` (`template_id`),
  CONSTRAINT `fk_system_dashboard_role_template_role` FOREIGN KEY (`role_id`) REFERENCES `system_role` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_system_dashboard_role_template_template` FOREIGN KEY (`template_id`) REFERENCES `system_dashboard_template` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Dashboard role default template binding table'
"""


CREATE_DASHBOARD_USER_CONFIG_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `system_dashboard_user_config` (
  `id` CHAR(36) NOT NULL DEFAULT (UUID()) PRIMARY KEY COMMENT 'Primary key',
  `is_del` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Soft delete flag',
  `created_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'Created time',
  `updated_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT 'Updated time',
  `user_id` CHAR(36) NOT NULL COMMENT 'User id',
  `template_id` CHAR(36) NULL COMMENT 'Template id used as source',
  `layout` JSON NULL COMMENT 'Personalized layout schema',
  `preferences` JSON NULL COMMENT 'Personalized preferences',
  UNIQUE KEY `uk_system_dashboard_user_config_user_id` (`user_id`),
  INDEX `idx_system_dashboard_user_config_template` (`template_id`),
  CONSTRAINT `fk_system_dashboard_user_config_user` FOREIGN KEY (`user_id`) REFERENCES `system_user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_system_dashboard_user_config_template` FOREIGN KEY (`template_id`) REFERENCES `system_dashboard_template` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Dashboard personalized user config table'
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


async def ensure_dashboard_schema() -> None:
    connection = connections.get("default")
    database_name = await fetch_current_database(connection)
    if not database_name:
        return

    table_names = [
        "system_dashboard_template",
        "system_dashboard_role_template",
        "system_dashboard_user_config",
    ]
    existing_tables = await fetch_existing_tables(connection, database_name, table_names)

    if "system_dashboard_template" not in existing_tables:
        await connection.execute_query(CREATE_DASHBOARD_TEMPLATE_TABLE_SQL)
    if "system_dashboard_role_template" not in existing_tables:
        await connection.execute_query(CREATE_DASHBOARD_ROLE_TEMPLATE_TABLE_SQL)
    if "system_dashboard_user_config" not in existing_tables:
        await connection.execute_query(CREATE_DASHBOARD_USER_CONFIG_TABLE_SQL)
