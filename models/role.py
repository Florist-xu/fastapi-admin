
from tortoise import fields
from models.common import BaseModel

class SystemRole(BaseModel):
    role_name = fields.CharField(max_length=255, null=False, description="角色名称")
    role_code = fields.CharField(max_length=255, null=False, description="角色编码")
    role_description = fields.CharField(max_length=255, null=True, description="角色描述")
    status = fields.SmallIntField(null=False, default=1, description="角色状态")
    # department = fields.ForeignKeyField("system.System_department", null=True, on_delete=fields.CASCADE, description="所属部门")
    class Meta:
        table = "system_role"
        table_description = "系统角色表"
        ordering = ["-created_at"]
