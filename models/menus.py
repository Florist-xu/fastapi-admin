from models.common import BaseModel
from tortoise import fields


class SystemPermission(BaseModel):
    menu_type = fields.SmallIntField(null=False, default=0, description="权限类型(0菜单、1按钮、2接口)")
    parent_id = fields.CharField(max_length=255, null=True, description="父权限ID")
    name = fields.CharField(max_length=255, null=True, description="权限名称/路由名称")
    path = fields.CharField(max_length=255, null=True, description="路由路径/接口路径")
    component = fields.CharField(max_length=255, null=True, description="前端组件路径")
    title = fields.CharField(max_length=255, null=True, description="菜单标题/权限名称")
    icon = fields.CharField(max_length=255, null=True, description="图标")
    api_path = fields.CharField(max_length=255, null=True, description="API接口路径(支持通配符,如 /api/user/*)")
    api_method = fields.JSONField(null=True, description="HTTP请求方法列表(如 ['GET', 'POST', 'PUT', 'DELETE'])")
    data_scope = fields.SmallIntField(null=True, default=4, description="数据权限范围(1全部、2本部门及下属、3仅本部门、4仅本人)")
    showBadge = fields.BooleanField(null=True, description="是否显示角标")
    showTextBadge = fields.CharField(max_length=255, null=True, description="显示的角标文本")
    isHide = fields.BooleanField(null=True, description="是否隐藏")
    isHideTab = fields.BooleanField(null=True, description="是否隐藏标签")
    link = fields.CharField(max_length=255, null=True, description="外部链接")
    isIframe = fields.BooleanField(null=True, description="是否内嵌iframe")
    keepAlive = fields.BooleanField(null=True, description="是否缓存")
    isFirstLevel = fields.BooleanField(null=True, description="是否一级菜单")
    fixedTab = fields.BooleanField(null=True, description="是否固定标签")
    activePath = fields.CharField(max_length=255, null=True, description="激活路径")
    isFullPage = fields.BooleanField(null=True, description="是否全屏")
    order = fields.IntField(null=True, default=999, description="排序")
    authTitle = fields.CharField(max_length=255, null=True, description="权限标题(按钮显示名称)")
    authMark = fields.CharField(max_length=255, null=True, description="权限标识(如 user:btn:add)")
    min_user_type = fields.SmallIntField(null=False, default=3, description="最低用户身份要求(0超级管理员,1管理员,2部门管理员,3普通用户)")
    remark = fields.CharField(max_length=500, null=True, description="备注说明")
    class Meta:
        table = "system_permission"
        table_description = "系统权限表"