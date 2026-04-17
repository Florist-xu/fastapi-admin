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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Dashboard role default template binding table';
