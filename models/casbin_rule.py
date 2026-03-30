from tortoise import fields
from models.common import BaseModel


class CasbinRule(BaseModel):
    ptype = fields.CharField(max_length=255, null=False, description="策略类型 (p=policy, g=grouping)")
    v0 = fields.CharField(max_length=255, null=True, description="第一个参数 (通常是 sub/角色)")
    v1 = fields.CharField(max_length=255, null=True, description="第二个参数 (通常是 obj/资源路径)")
    v2 = fields.CharField(max_length=255, null=True, description="第三个参数 (通常是 act/HTTP方法)")
    v3 = fields.CharField(max_length=255, null=True, description="第四个参数 (扩展字段)")
    v4 = fields.CharField(max_length=255, null=True, description="第五个参数 (扩展字段)")
    v5 = fields.CharField(max_length=255, null=True, description="第六个参数 (扩展字段)")
    
    class Meta:
        table = "casbin_rule"
        table_description = "Casbin规则表"
        ordering = ["-created_at"]