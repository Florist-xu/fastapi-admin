from typing import List

from fastapi import APIRouter, Depends
from tortoise.expressions import Q

from fields.role import Role, RoleBase, RolePermissionUpdate
from models.casbin_rule import CasbinRule
from models.department import SystemDepartment
from models.menus import SystemPermission
from models.role import SystemRole
from utils.pagination import PageParams, get_page_params, paginate
from utils.response import ResponseUtil

roleAPI = APIRouter(prefix="/role", tags=["role"])


@roleAPI.get("/list")
async def get_all_role(page: PageParams = Depends(get_page_params)):
    data = await paginate(SystemRole.all(), page.current, page.size)
    for i in range(len(data["records"])):
        item = data["records"][i]
        dept = await SystemDepartment.filter(id=item.department_id).first()
        item_dict = {
            "id": item.id,
            "name": item.name,
            "code": item.code,
            "description": item.description,
            "status": bool(item.status),
            "department_id": item.department_id,
            "department_name": dept.name if dept else "",
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
        data["records"][i] = item_dict

    return ResponseUtil.success(data=data)


@roleAPI.post("/add")
async def add_role(role: RoleBase):
    await SystemRole.create(**role.model_dump())
    return ResponseUtil.success()


@roleAPI.delete("/delete")
async def delete_role(role: Role):
    try:
        await SystemRole.filter(id=role.id).delete()
        return ResponseUtil.success()
    except Exception:
        return ResponseUtil.error()


@roleAPI.put("/update/{role_id}")
async def update_role(role_id: str, role: RoleBase):
    update_data = role.model_dump(exclude_none=True)
    await SystemRole.filter(id=role_id).update(**update_data)
    return ResponseUtil.success()


@roleAPI.get("/permissionList/{role_id}")
async def get_user_permissions_list(role_id: str):
    role = await SystemRole.filter(id=role_id, is_del=False).first()
    if not role:
        return ResponseUtil.error(msg="角色信息不存在")

    permissions = await CasbinRule.filter(v0=role.code, is_del=False).all()
    if not permissions:
        return ResponseUtil.error(msg="用户权限不存在")

    v1_set = {p.v1 for p in permissions if p.v1}
    if not v1_set:
        return ResponseUtil.success(data={"actual_permission_ids": []})

    permission_rows = await SystemPermission.filter(is_del=False).filter(
        Q(id__in=v1_set) | Q(api_path__in=v1_set)
    ).values("id")
    permission_map = [row["id"] for row in permission_rows if row.get("id")]
    return ResponseUtil.success(data={"actual_permission_ids": permission_map})


@roleAPI.post("/updatePermission/{role_id}")
async def update_role_permission(role_id: str, payload: RolePermissionUpdate):
    role = await SystemRole.filter(id=role_id, is_del=False).first()
    if not role:
        return ResponseUtil.error(msg="角色信息不存在")

    # De-duplicate the requested permission ids before comparing with history.
    target_permission_ids = [
        str(permission_id)
        for permission_id in dict.fromkeys(payload.permission_ids)
        if permission_id is not None
    ]

    # Load all historical rules, including soft-deleted rows, so we can restore old
    # records instead of creating duplicates for the same role + permission pair.
    existing_rules = await CasbinRule.filter(v0=role.code).order_by("created_at").all()
    rules_by_permission_id = {}
    for rule in existing_rules:
        if rule.v1:
            rules_by_permission_id.setdefault(str(rule.v1), []).append(rule)

    for permission_id, rules in rules_by_permission_id.items():
        # If duplicates already exist historically, keep the oldest one as the
        # canonical row and soft-delete the rest.
        primary_rule = rules[0]
        duplicate_rules = rules[1:]

        for duplicate_rule in duplicate_rules:
            if not duplicate_rule.is_del:
                await CasbinRule.filter(id=duplicate_rule.id).update(is_del=True)

        # Restore selected permissions and soft-delete unselected ones.
        if permission_id in target_permission_ids:
            if primary_rule.is_del:
                await CasbinRule.filter(id=primary_rule.id).update(is_del=False)
        elif not primary_rule.is_del:
            await CasbinRule.filter(id=primary_rule.id).update(is_del=True)

    # Only create rows for permissions that have never existed before.
    new_permission_ids = [
        permission_id
        for permission_id in target_permission_ids
        if permission_id not in rules_by_permission_id
    ]
    if new_permission_ids:
        await CasbinRule.bulk_create(
            [
                CasbinRule(
                    ptype="p",
                    v0=role.code,
                    v1=permission_id,
                    is_del=False,
                )
                for permission_id in new_permission_ids
            ]
        )

    return ResponseUtil.success()
