from tortoise import fields

from models.common import BaseModel


class SystemUser(BaseModel):
    username = fields.CharField(max_length=255, null=False, description="用户名")
    password = fields.CharField(max_length=255, null=False, description="密码")
    email = fields.CharField(max_length=255, null=True, description="邮箱")
    phone = fields.CharField(max_length=30, null=True, description="手机号")
    nickname = fields.CharField(max_length=255, null=True, description="昵称")
    avatar = fields.CharField(max_length=512, null=True, description="头像")
    gender = fields.SmallIntField(null=False, default=0, description="性别(0未知,1男,2女)")
    status = fields.SmallIntField(null=False, default=1, description="用户状态(1启用,0禁用)")
    user_type = fields.SmallIntField(
        null=False,
        default=3,
        description="用户身份标识",
    )

    class Meta:
        table = "system_user"
        table_description = "用户表"
        ordering = ["-created_at"]


class SystemUserRole(BaseModel):
    role_id = fields.ForeignKeyField(
        "system.SystemRole",
        null=True,
        on_delete=fields.CASCADE,
        source_field="role_id",
    )
    user_id = fields.ForeignKeyField(
        "system.SystemUser",
        null=True,
        on_delete=fields.CASCADE,
        source_field="user_id",
        description="用户ID",
    )

    class Meta:
        table = "system_user_role"
        table_description = "用户角色表"
