from tortoise import fields

from models.common import BaseModel


class SystemOperationLog(BaseModel):
    operation_name = fields.CharField(max_length=255, description="操作名称")
    operation_type = fields.SmallIntField(description="操作类型")
    request_path = fields.TextField(description="请求路径")
    request_method = fields.CharField(max_length=10, description="请求方法")
    host = fields.CharField(max_length=50, description="主机地址")
    location = fields.CharField(max_length=255, null=True, description="操作地点")
    user_agent = fields.TextField(null=True, description="用户请求头")
    browser = fields.CharField(max_length=255, null=True, description="浏览器类型")
    os = fields.CharField(max_length=255, null=True, description="操作系统")
    request_params = fields.TextField(description="请求参数")
    response_result = fields.TextField(null=True, description="返回结果")
    status = fields.SmallIntField(description="操作状态")
    cost_time = fields.FloatField(description="消耗时间")
    operator_id = fields.CharField(max_length=36, null=True, description="操作人员")

    class Meta:
        table = "system_operation_log"
        table_description = "系统操作日志表"
