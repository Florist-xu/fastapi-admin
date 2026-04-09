from tortoise import fields

from models.common import BaseModel


class SystemArticle(BaseModel):
    title = fields.CharField(max_length=255, null=False, description="Article title")
    summary = fields.TextField(null=True, description="Article summary")
    cover = fields.CharField(max_length=512, null=True, description="Cover url")
    content = fields.TextField(null=False, description="Article content")
    content_text = fields.TextField(null=True, description="Plain text content")
    category_id = fields.CharField(max_length=36, null=True, description="Category id")
    category_name = fields.CharField(max_length=255, null=True, description="Category name")
    tag_ids = fields.JSONField(null=True, default=list, description="Tag id list")
    tag_names = fields.JSONField(null=True, default=list, description="Tag name list")
    status = fields.SmallIntField(null=False, default=0, description="0 draft 1 published")
    published_at = fields.DatetimeField(null=True, description="Published time")
    author_id = fields.CharField(max_length=36, null=True, description="Author id")
    author_name = fields.CharField(max_length=255, null=True, description="Author name")
    sort = fields.IntField(null=False, default=0, description="Sort value")
    is_top = fields.BooleanField(null=False, default=False, description="Is top")
    view_count = fields.IntField(null=False, default=0, description="View count")
    remark = fields.CharField(max_length=500, null=True, description="Remark")

    class Meta:
        table = "system_article"
        table_description = "Article"
        ordering = ["-is_top", "sort", "-published_at", "-created_at"]
