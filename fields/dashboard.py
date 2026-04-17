from typing import Any

from pydantic import BaseModel, Field, field_validator


def _normalize_role_ids(value: list[str]) -> list[str]:
    return [item for item in dict.fromkeys(str(item).strip() for item in value if str(item).strip())]


class DashboardLayoutSave(BaseModel):
    layout: list[dict[str, Any]] = Field(default_factory=list)
    template_id: str | None = None
    preferences: dict[str, Any] | None = None

    @field_validator("layout")
    @classmethod
    def validate_layout(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return value or []


class DashboardTemplateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    layout: list[dict[str, Any]] = Field(default_factory=list)
    role_ids: list[str] = Field(default_factory=list)
    priority: int = 100
    is_public: bool = True
    status: int = 1
    theme_config: dict[str, Any] | None = None
    template_key: str | None = Field(default=None, max_length=120)

    @field_validator("role_ids")
    @classmethod
    def normalize_role_ids(cls, value: list[str]) -> list[str]:
        return _normalize_role_ids(value)


class DashboardTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    layout: list[dict[str, Any]] | None = None
    role_ids: list[str] | None = None
    priority: int | None = None
    is_public: bool | None = None
    status: int | None = None
    theme_config: dict[str, Any] | None = None
    template_key: str | None = Field(default=None, max_length=120)

    @field_validator("role_ids")
    @classmethod
    def normalize_role_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return _normalize_role_ids(value)
