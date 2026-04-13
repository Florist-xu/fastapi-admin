from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field, field_validator


def normalize_type(value: Optional[int | str], default: int = 2) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result in {0, 1, 2} else default


def normalize_scope(value: Optional[int | str], default: int = 0) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result in {0, 1, 2} else default


def normalize_status(value: Optional[int | str], default: int = 0) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result in {0, 1, 2} else default


class NotificationCreate(BaseModel):
    title: str
    summary: Optional[str] = None
    content: str
    type: int = 2
    scope: int = 0
    scope_ids: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("scope_ids", "scopeIds"),
    )
    priority: int = 0
    status: int = 0
    expire_time: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("expire_time", "expireTime"),
    )
    publish_now: bool = Field(
        default=False,
        validation_alias=AliasChoices("publish_now", "publishNow"),
    )

    category: Optional[str] = None
    target_type: Optional[str] = None
    target_user_ids: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("target_user_ids", "targetUserIds"),
    )
    target_user_types: list[int] = Field(
        default_factory=list,
        validation_alias=AliasChoices("target_user_types", "targetUserTypes"),
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("expires_at", "expiresAt"),
    )

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, value: int | str) -> int:
        return normalize_type(value)

    @field_validator("scope", mode="before")
    @classmethod
    def validate_scope(cls, value: int | str) -> int:
        return normalize_scope(value)

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: int | str) -> int:
        return normalize_status(value)


class NotificationUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    type: Optional[int] = None
    scope: Optional[int] = None
    scope_ids: Optional[list[str]] = Field(
        default=None,
        validation_alias=AliasChoices("scope_ids", "scopeIds"),
    )
    priority: Optional[int] = None
    status: Optional[int] = None
    expire_time: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("expire_time", "expireTime"),
    )

    category: Optional[str] = None
    target_type: Optional[str] = None
    target_user_ids: Optional[list[str]] = Field(
        default=None,
        validation_alias=AliasChoices("target_user_ids", "targetUserIds"),
    )
    target_user_types: Optional[list[int]] = Field(
        default=None,
        validation_alias=AliasChoices("target_user_types", "targetUserTypes"),
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("expires_at", "expiresAt"),
    )

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, value: Optional[int | str]) -> Optional[int]:
        if value is None:
            return value
        return normalize_type(value)

    @field_validator("scope", mode="before")
    @classmethod
    def validate_scope(cls, value: Optional[int | str]) -> Optional[int]:
        if value is None:
            return value
        return normalize_scope(value)

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: Optional[int | str]) -> Optional[int]:
        if value is None:
            return value
        return normalize_status(value)


class NotificationReadAll(BaseModel):
    category: Optional[str] = None
