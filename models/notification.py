from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields

from models.common import BaseModel

if TYPE_CHECKING:
    from models.user import SystemUser
    from tortoise.fields.relational import ForeignKeyNullableRelation, ForeignKeyRelation


class SystemNotification(BaseModel):
    title = fields.CharField(max_length=200, null=False, description="通知标题")
    content = fields.TextField(null=False, description="通知内容")
    type = fields.SmallIntField(default=2, description="通知类型 0登录通知 1公告通知 2系统消息")
    scope = fields.SmallIntField(default=0, description="通知范围 0全部 1按部门 2指定用户")
    scope_ids = fields.JSONField(null=True, description="范围ID列表")
    status = fields.SmallIntField(default=0, description="状态 0草稿 1发布 2撤回")
    priority = fields.SmallIntField(default=0, description="优先级")
    publish_time = fields.DatetimeField(null=True, description="发布时间")
    expire_time = fields.DatetimeField(null=True, description="过期时间")
    creator_id = fields.CharField(max_length=36, null=True, description="创建者")

    class Meta:
        table = "system_notification"
        table_description = "系统通知表"
        ordering = ["-created_at"]


class SystemUserNotification(BaseModel):
    notification_id: str | None
    user_id: str | None
    notification: ForeignKeyRelation[SystemNotification]
    user: ForeignKeyNullableRelation[SystemUser]

    notification = fields.ForeignKeyField(
        "system.SystemNotification",
        related_name="deliveries",
        on_delete=fields.CASCADE,
        source_field="notification_id",
        description="通知ID",
    )
    user = fields.ForeignKeyField(
        "system.SystemUser",
        related_name="notifications",
        null=True,
        on_delete=fields.CASCADE,
        source_field="user_id",
        description="接收用户ID",
    )
    is_read = fields.BooleanField(default=False, description="是否已读")
    read_at = fields.DatetimeField(null=True, description="已读时间")
    delivered_at = fields.DatetimeField(auto_now_add=True, null=True, description="投递时间")

    class Meta:
        table = "system_user_notification"
        table_description = "用户通知投递表"
        ordering = ["is_read", "-delivered_at"]
