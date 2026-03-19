from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel


class RoleBase(BaseModel):
    """角色基础模型，包含公共字段"""
    role_name: Optional[str] = None
    role_code: Optional[str] = None
    role_description: Optional[str] = None
    status: Optional[int] = None


class Role(RoleBase):
    id: UUID  

