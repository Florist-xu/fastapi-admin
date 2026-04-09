from pydantic import BaseModel, Field, field_validator


def normalize_tag_ids(values: list[str] | None) -> list[str]:
    if not values:
        return []
    normalized = [item.strip() for item in values if isinstance(item, str) and item.strip()]
    return list(dict.fromkeys(normalized))


class ArticleBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=2000)
    cover: str | None = Field(default=None, max_length=512)
    content: str = Field(..., min_length=1)
    category_id: str | None = Field(default=None, max_length=36)
    tag_ids: list[str] = Field(default_factory=list)
    status: int = Field(default=0, description="0 draft 1 published")
    sort: int = Field(default=0)
    is_top: bool = Field(default=False)
    remark: str | None = Field(default=None, max_length=500)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: int) -> int:
        if value not in (0, 1):
            raise ValueError("status can only be 0 or 1")
        return value

    @field_validator("tag_ids")
    @classmethod
    def validate_tag_ids(cls, value: list[str]) -> list[str]:
        return normalize_tag_ids(value)


class ArticleCreate(ArticleBase):
    pass


class ArticleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=2000)
    cover: str | None = Field(default=None, max_length=512)
    content: str | None = Field(default=None, min_length=1)
    category_id: str | None = Field(default=None, max_length=36)
    tag_ids: list[str] | None = Field(default=None)
    status: int | None = Field(default=None, description="0 draft 1 published")
    sort: int | None = Field(default=None)
    is_top: bool | None = Field(default=None)
    remark: str | None = Field(default=None, max_length=500)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: int | None) -> int | None:
        if value is not None and value not in (0, 1):
            raise ValueError("status can only be 0 or 1")
        return value

    @field_validator("tag_ids")
    @classmethod
    def validate_tag_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        return normalize_tag_ids(value)


class ArticlePublish(BaseModel):
    status: int = Field(default=1, description="0 offline 1 published")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: int) -> int:
        if value not in (0, 1):
            raise ValueError("status can only be 0 or 1")
        return value
