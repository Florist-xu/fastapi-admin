from tortoise import connections


CREATE_RUNTIME_MODULE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `system_runtime_module` (
  `id` CHAR(36) NOT NULL DEFAULT (UUID()) PRIMARY KEY COMMENT 'Primary key',
  `is_del` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Soft delete flag',
  `created_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'Created time',
  `updated_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT 'Updated time',
  `code` VARCHAR(100) NOT NULL COMMENT 'Module code',
  `name` VARCHAR(255) NOT NULL COMMENT 'Module name',
  `version` VARCHAR(50) NOT NULL DEFAULT '1.0.0' COMMENT 'Module version',
  `description` TEXT NULL COMMENT 'Module description',
  `author` VARCHAR(255) NULL COMMENT 'Module author',
  `source_type` VARCHAR(30) NOT NULL DEFAULT 'upload' COMMENT 'upload/example',
  `package_name` VARCHAR(100) NOT NULL COMMENT 'Python package name',
  `entry_module` VARCHAR(100) NOT NULL DEFAULT 'module' COMMENT 'Entry module',
  `class_name` VARCHAR(100) NOT NULL DEFAULT 'Module' COMMENT 'Entry class',
  `archive_path` VARCHAR(500) NULL COMMENT 'Uploaded archive path',
  `install_path` VARCHAR(500) NOT NULL COMMENT 'Installed module path',
  `status` SMALLINT NOT NULL DEFAULT 0 COMMENT '0 unloaded 1 loaded',
  `manifest` JSON NULL COMMENT 'Manifest json',
  `config` JSON NULL COMMENT 'Config json',
  `route_count` INT NOT NULL DEFAULT 0 COMMENT 'Loaded route count',
  `installed_by` VARCHAR(36) NULL COMMENT 'Installer user id',
  `installed_by_name` VARCHAR(255) NULL COMMENT 'Installer user name',
  `last_loaded_at` DATETIME(6) NULL COMMENT 'Last loaded time',
  `last_unloaded_at` DATETIME(6) NULL COMMENT 'Last unloaded time',
  `last_error` TEXT NULL COMMENT 'Last runtime error',
  UNIQUE KEY `uk_system_runtime_module_code` (`code`),
  INDEX `idx_system_runtime_module_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Runtime pluggable module'
"""


async def fetch_current_database(connection) -> str:
    rows = await connection.execute_query_dict("SELECT DATABASE() AS db_name")
    if not rows:
        return ""
    return rows[0].get("db_name") or ""


async def runtime_module_table_exists(connection, database_name: str) -> bool:
    rows = await connection.execute_query_dict(
        """
        SELECT TABLE_NAME
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """,
        [database_name, "system_runtime_module"],
    )
    return bool(rows)


async def ensure_runtime_module_schema() -> None:
    connection = connections.get("default")
    database_name = await fetch_current_database(connection)
    if not database_name:
        return

    if not await runtime_module_table_exists(connection, database_name):
        await connection.execute_query(CREATE_RUNTIME_MODULE_TABLE_SQL)
