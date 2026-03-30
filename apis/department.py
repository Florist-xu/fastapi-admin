from fastapi import APIRouter

from models.department import SystemDepartment
from fields.deparment import DepartmentBase
from utils.response import ResponseUtil


departmentAPI = APIRouter(prefix="/department", tags=["部门"])


@departmentAPI.get("/tree")
async def tree():
    rows = await SystemDepartment.filter(is_del=False).values()
    node_map = {str(row["id"]): {**row, "children": []} for row in rows}

    tree_data = []
    for row in node_map.values():
        parent_id = row.get("parent_id")
        parent_key = str(parent_id) if parent_id else None
        
        if parent_key and parent_key in node_map:
            node_map[parent_key]["children"].append(row)
            # 子节点排序
            node_map[parent_key]["children"].sort(key=lambda x: x.get("sort", 0))
        else:
            tree_data.append(row)
    
    # 顶级节点排序
    tree_data.sort(key=lambda x: x.get("sort", 0))

    return ResponseUtil.success(data=tree_data)


# 编辑
@departmentAPI.put("/{id}")
async def edit(id: str, department: DepartmentBase):
    await SystemDepartment.filter(id=id).update(**department.model_dump())
    return ResponseUtil.success()


# 删除
@departmentAPI.delete("/{id}")
async def delete(id: str):
    await SystemDepartment.filter(id=id).update(is_del=True)
    return ResponseUtil.success()


# 新增
@departmentAPI.post("/add")
async def add(department: DepartmentBase):
    await SystemDepartment.create(**department.model_dump())
    return ResponseUtil.success()
