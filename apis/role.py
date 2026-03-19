from fastapi import APIRouter, Depends
from models.role import SystemRole
from fields.role import RoleBase,Role
from utils.response import ResponseUtil
from utils.pagination import get_page_params, paginate, PageParams

roleAPI = APIRouter(prefix="/role",tags=["role"])

# 所有角色
@roleAPI.get("/list")
async def get_all_role(page: PageParams = Depends(get_page_params)):
    data = await paginate(SystemRole.all(), page.current, page.size)
    # 将status字段转换为布尔值
    for record in data["records"]:
        record.status = bool(record.status)
    
    return ResponseUtil.success(data=data)


@roleAPI.post("/add")
async def add_role(role: RoleBase):
    await SystemRole.create(**role.model_dump())

    return ResponseUtil.success()

# 删除角色
@roleAPI.delete("/delete")
async def delete_role(role:Role):
    # print(id,"角儿id")
    try:
        await SystemRole.filter(id=role.id).delete()
        return ResponseUtil.success()
    except Exception:
        return ResponseUtil.error()

# 修改角色
@roleAPI.put("/update/{role_id}")
async def update_role(role_id: str, role: RoleBase):
    update_data = role.model_dump(exclude_none=True)
    await SystemRole.filter(id=role_id).update(**update_data)

    return ResponseUtil.success()


