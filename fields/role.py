from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field


class RoleBase(BaseModel):
    """角色基础模型，包含公共字段"""
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    status: Optional[int] = None


class Role(RoleBase):
    id: UUID  


class RolePermissionUpdate(BaseModel):
    permission_ids: list[str] = Field(default_factory=list)

