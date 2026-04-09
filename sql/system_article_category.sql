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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Article category table';
