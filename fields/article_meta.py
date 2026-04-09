from pydantic import BaseModel, Field, field_validator


class ArticleCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    status: int = Field(default=1, description="1 enabled 0 disabled")
    sort: int = Field(default=0)
    remark: str | None = Field(default=None, max_length=500)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: int) -> int:
        if value not in (0, 1):
            raise ValueError("status can only be 0 or 1")
        return value


class ArticleCategoryCreate(ArticleCategoryBase):
    pass


class ArticleCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: int | None = Field(default=None, description="1 enabled 0 disabled")
    sort: int | None = Field(default=None)
    remark: str | None = Field(default=None, max_length=500)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: int | None) -> int | None:
        if value is not None and value not in (0, 1):
            raise ValueError("status can only be 0 or 1")
        return value


class ArticleTagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    color: str = Field(default="#409EFF", min_length=4, max_length=20)
    status: int = Field(default=1, description="1 enabled 0 disabled")
    sort: int = Field(default=0)
    remark: str | None = Field(default=None, max_length=500)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: int) -> int:
        if value not in (0, 1):
            raise ValueError("status can only be 0 or 1")
        return value


class ArticleTagCreate(ArticleTagBase):
    pass


class ArticleTagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    color: str | None = Field(default=None, min_length=4, max_length=20)
    status: int | None = Field(default=None, description="1 enabled 0 disabled")
    sort: int | None = Field(default=None)
    remark: str | None = Field(default=None, max_length=500)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: int | None) -> int | None:
        if value is not None and value not in (0, 1):
            raise ValueError("status can only be 0 or 1")
        return value
