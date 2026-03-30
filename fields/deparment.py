from typing import Optional
from pydantic import BaseModel
from uuid import UUID
class DepartmentBase(BaseModel):
    name: str
    parent_id: Optional[str] = None
    sort: int = 0
    phone: Optional[str] = None
    principal: str
    email: Optional[str] = None
    status: int = 1
    remark: Optional[str] = None

class DepartmentOut(BaseModel):
    id: Optional[UUID] = None