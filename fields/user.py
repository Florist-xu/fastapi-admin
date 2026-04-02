from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import AliasChoices, BaseModel, Field, field_validator


class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    phone: Optional[str] = None
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    gender: int = 0
    status: int = 1
    user_type: int = 3
    department_id: Optional[str] = None


class UserOut(BaseModel):
    id: Optional[UUID] = None
    is_del: Optional[bool] = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    gender: int = 0
    status: int = 1
    user_type: int = 3
    department_id: Optional[str] = None


# 编辑
class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    gender: Optional[int] = None
    status: Optional[int] = None
    user_type: Optional[int] = None
    department_id: Optional[str] = None

class deleteUser(BaseModel):
    id: UUID


class UserLogin(BaseModel):
    username: str = Field(validation_alias=AliasChoices("username", "userName"))
    password: str


class RefreshTokenIn(BaseModel):
    refreshToken: str


class UserRoleUpdate(BaseModel):
    user_id: str = Field(validation_alias=AliasChoices("user_id", "userId"))
    role_ids: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("role_ids", "roleIds"),
    )

    @field_validator("role_ids", mode="before")
    @classmethod
    def normalize_role_ids(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value
    
