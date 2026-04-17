from tortoise import fields

from models.common import BaseModel


class SystemDashboardTemplate(BaseModel):
    name = fields.CharField(max_length=120, null=False, description="Template name")
    template_key = fields.CharField(max_length=120, null=True, description="Template key")
    description = fields.CharField(max_length=500, null=True, description="Template description")
    layout = fields.JSONField(null=False, description="Dashboard layout schema")
    theme_config = fields.JSONField(null=True, description="Theme config")
    is_public = fields.BooleanField(default=True, description="Whether template is public")
    status = fields.SmallIntField(default=1, description="Template status")
    created_by = fields.CharField(max_length=36, null=True, description="Creator user id")
    created_by_name = fields.CharField(max_length=255, null=True, description="Creator display name")
    updated_by = fields.CharField(max_length=36, null=True, description="Last updater user id")
    updated_by_name = fields.CharField(max_length=255, null=True, description="Last updater display name")

    class Meta:
        table = "system_dashboard_template"
        table_description = "Dashboard template"
        ordering = ["-updated_at", "-created_at"]


class SystemDashboardRoleTemplate(BaseModel):
    role_id = fields.CharField(max_length=36, null=False, description="Role id")
    template_id = fields.CharField(max_length=36, null=False, description="Template id")
    priority = fields.IntField(default=100, description="Binding priority, lower wins")

    class Meta:
        table = "system_dashboard_role_template"
        table_description = "Dashboard role default template binding"
        ordering = ["priority", "-updated_at", "-created_at"]


class SystemDashboardUserConfig(BaseModel):
    user_id = fields.CharField(max_length=36, null=False, unique=True, description="User id")
    template_id = fields.CharField(max_length=36, null=True, description="Template id used as source")
    layout = fields.JSONField(null=True, description="Personalized dashboard layout")
    preferences = fields.JSONField(null=True, description="Personalized preferences")

    class Meta:
        table = "system_dashboard_user_config"
        table_description = "Dashboard personalized user config"
        ordering = ["-updated_at", "-created_at"]
