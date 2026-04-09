ALTER TABLE `system_article`
  ADD COLUMN IF NOT EXISTS `category_id` VARCHAR(36) NULL COMMENT 'Category id' AFTER `content_text`,
  ADD COLUMN IF NOT EXISTS `category_name` VARCHAR(255) NULL COMMENT 'Category name' AFTER `category_id`,
  ADD COLUMN IF NOT EXISTS `tag_ids` JSON NULL COMMENT 'Tag ids' AFTER `category_name`,
  ADD COLUMN IF NOT EXISTS `tag_names` JSON NULL COMMENT 'Tag names' AFTER `tag_ids`;
