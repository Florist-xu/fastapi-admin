from tortoise import fields

from models.common import BaseModel


class SystemArticleCategory(BaseModel):
    name = fields.CharField(max_length=255, null=False, description="Category name")
    status = fields.SmallIntField(null=False, default=1, description="1 enabled 0 disabled")
    sort = fields.IntField(null=False, default=0, description="Sort value")
    remark = fields.CharField(max_length=500, null=True, description="Remark")

    class Meta:
        table = "system_article_category"
        table_description = "Article category"
        ordering = ["-status", "sort", "-created_at"]


class SystemArticleTag(BaseModel):
    name = fields.CharField(max_length=255, null=False, description="Tag name")
    color = fields.CharField(max_length=20, null=False, default="#409EFF", description="Tag color")
    status = fields.SmallIntField(null=False, default=1, description="1 enabled 0 disabled")
    sort = fields.IntField(null=False, default=0, description="Sort value")
    remark = fields.CharField(max_length=500, null=True, description="Remark")

    class Meta:
        table = "system_article_tag"
        table_description = "Article tag"
        ordering = ["-status", "sort", "-created_at"]
