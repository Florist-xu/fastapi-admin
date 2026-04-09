from tortoise import connections


CREATE_ARTICLE_CATEGORY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `system_article_category` (
  `id` CHAR(36) NOT NULL DEFAULT (UUID()) PRIMARY KEY COMMENT 'Primary key',
  `is_del` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Soft delete flag',
  `created_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'Created time',
  `updated_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT 'Updated time',
  `name` VARCHAR(255) NOT NULL COMMENT 'Category name',
  `status` SMALLINT NOT NULL DEFAULT 1 COMMENT '1 enabled 0 disabled',
  `sort` INT NOT NULL DEFAULT 0 COMMENT 'Sort value',
  `remark` VARCHAR(500) NULL COMMENT 'Remark',
  INDEX `idx_system_article_category_name` (`name`),
  INDEX `idx_system_article_category_status` (`status`),
  INDEX `idx_system_article_category_sort` (`sort`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Article category table'
"""

CREATE_ARTICLE_TAG_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `system_article_tag` (
  `id` CHAR(36) NOT NULL DEFAULT (UUID()) PRIMARY KEY COMMENT 'Primary key',
  `is_del` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Soft delete flag',
  `created_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT 'Created time',
  `updated_at` DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT 'Updated time',
  `name` VARCHAR(255) NOT NULL COMMENT 'Tag name',
  `color` VARCHAR(20) NOT NULL DEFAULT '#409EFF' COMMENT 'Tag color',
  `status` SMALLINT NOT NULL DEFAULT 1 COMMENT '1 enabled 0 disabled',
  `sort` INT NOT NULL DEFAULT 0 COMMENT 'Sort value',
  `remark` VARCHAR(500) NULL COMMENT 'Remark',
  INDEX `idx_system_article_tag_name` (`name`),
  INDEX `idx_system_article_tag_status` (`status`),
  INDEX `idx_system_article_tag_sort` (`sort`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Article tag table'
"""

ARTICLE_COLUMN_FIXES = {
    "category_id": "ALTER TABLE `system_article` ADD COLUMN `category_id` VARCHAR(36) NULL COMMENT 'Category id' AFTER `content_text`",
    "category_name": "ALTER TABLE `system_article` ADD COLUMN `category_name` VARCHAR(255) NULL COMMENT 'Category name' AFTER `category_id`",
    "tag_ids": "ALTER TABLE `system_article` ADD COLUMN `tag_ids` JSON NULL COMMENT 'Tag ids' AFTER `category_name`",
    "tag_names": "ALTER TABLE `system_article` ADD COLUMN `tag_names` JSON NULL COMMENT 'Tag names' AFTER `tag_ids`",
}

ARTICLE_INDEX_FIXES = {
    "idx_system_article_category_id": "ALTER TABLE `system_article` ADD INDEX `idx_system_article_category_id` (`category_id`)",
}


async def fetch_current_database(connection) -> str:
    rows = await connection.execute_query_dict("SELECT DATABASE() AS db_name")
    if not rows:
        return ""
    return rows[0].get("db_name") or ""


async def fetch_table_columns(connection, database_name: str, table_name: str) -> set[str]:
    rows = await connection.execute_query_dict(
        """
        SELECT COLUMN_NAME
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """,
        [database_name, table_name],
    )
    return {row["COLUMN_NAME"] for row in rows}


async def fetch_existing_tables(
    connection, database_name: str, table_names: list[str]
) -> set[str]:
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


async def fetch_table_indexes(connection, table_name: str) -> set[str]:
    rows = await connection.execute_query_dict(f"SHOW INDEX FROM `{table_name}`")
    return {row["Key_name"] for row in rows}


async def ensure_article_taxonomy_schema() -> None:
    connection = connections.get("default")
    database_name = await fetch_current_database(connection)
    if not database_name:
        return

    existing_tables = await fetch_existing_tables(
        connection,
        database_name,
        ["system_article_category", "system_article_tag"],
    )
    if "system_article_category" not in existing_tables:
        await connection.execute_query(CREATE_ARTICLE_CATEGORY_TABLE_SQL)
    if "system_article_tag" not in existing_tables:
        await connection.execute_query(CREATE_ARTICLE_TAG_TABLE_SQL)

    existing_columns = await fetch_table_columns(connection, database_name, "system_article")
    for column_name, alter_sql in ARTICLE_COLUMN_FIXES.items():
        if column_name not in existing_columns:
            await connection.execute_query(alter_sql)

    existing_indexes = await fetch_table_indexes(connection, "system_article")
    for index_name, alter_sql in ARTICLE_INDEX_FIXES.items():
        if index_name not in existing_indexes:
            await connection.execute_query(alter_sql)
