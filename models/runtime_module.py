from tortoise import fields

from models.common import BaseModel


class SystemRuntimeModule(BaseModel):
    code = fields.CharField(max_length=100, null=False, unique=True, description="Module code")
    name = fields.CharField(max_length=255, null=False, description="Module name")
    version = fields.CharField(max_length=50, null=False, default="1.0.0", description="Module version")
    description = fields.TextField(null=True, description="Module description")
    author = fields.CharField(max_length=255, null=True, description="Module author")
    source_type = fields.CharField(max_length=30, null=False, default="upload", description="upload/example")
    package_name = fields.CharField(max_length=100, null=False, description="Python package name")
    entry_module = fields.CharField(max_length=100, null=False, default="module", description="Entry module")
    class_name = fields.CharField(max_length=100, null=False, default="Module", description="Entry class")
    archive_path = fields.CharField(max_length=500, null=True, description="Uploaded archive path")
    install_path = fields.CharField(max_length=500, null=False, description="Installed module path")
    status = fields.SmallIntField(null=False, default=0, description="0 unloaded 1 loaded")
    manifest = fields.JSONField(null=True, default=dict, description="Module manifest")
    config = fields.JSONField(null=True, default=dict, description="Module config")
    route_count = fields.IntField(null=False, default=0, description="Loaded route count")
    installed_by = fields.CharField(max_length=36, null=True, description="Installer user id")
    installed_by_name = fields.CharField(max_length=255, null=True, description="Installer user name")
    last_loaded_at = fields.DatetimeField(null=True, description="Last loaded time")
    last_unloaded_at = fields.DatetimeField(null=True, description="Last unloaded time")
    last_error = fields.TextField(null=True, description="Last runtime error")

    class Meta:
        table = "system_runtime_module"
        table_description = "Runtime pluggable module"
        ordering = ["-created_at"]
