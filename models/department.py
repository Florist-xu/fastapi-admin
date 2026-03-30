
from tortoise import fields

from models.common import BaseModel

class SystemDepartment(BaseModel):

    name = fields.CharField(max_length=50, null=False, description="部门名称")
    parent_id = fields.CharField(max_length=50, null=True, description="上级部门ID")
    sort = fields.IntField(null=False, default=0, description="排序权重（0最高）")
    phone = fields.CharField(max_length=30, null=True, description="部门电话")
    principal = fields.CharField(max_length=64, null=False, description="部门负责人")
    email = fields.CharField(max_length=128, null=True, description="部门邮箱")
    status = fields.SmallIntField(null=False, default=1, description="状态（0正常 1停用）")
    remark = fields.CharField(max_length=255, null=True, description="备注信息")
    class Meta:
        table = "system_department"
        table_description = "系统部门表"
        ordering = ["sort", "-created_at"]
