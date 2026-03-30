
from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields
from models.common import BaseModel

if TYPE_CHECKING:
    from models.department import SystemDepartment
    from tortoise.fields.relational import ForeignKeyNullableRelation

class SystemRole(BaseModel):
    department_id: str | None
    department: ForeignKeyNullableRelation[SystemDepartment]
    name = fields.CharField(max_length=255, null=False,source_field="role_name",description="角色名称")
    code = fields.CharField(max_length=255, null=False,source_field="role_code", description="角色编码")
    description = fields.CharField(max_length=255, null=True,source_field="role_description", description="角色描述")
    status = fields.SmallIntField(null=False, default=1,source_field="status", description="角色状态")
    department = fields.ForeignKeyField("system.SystemDepartment",source_field="department_id", null=True, description="所属部门")
    class Meta:
        table = "system_role"
        table_description = "系统角色表"
        ordering = ["-created_at"]
