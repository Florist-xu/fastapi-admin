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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Dashboard personalized user config table';
