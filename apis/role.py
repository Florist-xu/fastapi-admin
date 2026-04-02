from typing import List

from fastapi import APIRouter, Depends
from tortoise.expressions import Q

from fields.role import Role, RoleBase, RolePermissionUpdate
from models.casbin_rule import CasbinRule
from models.department import SystemDepartment
from models.menus import SystemPermission
from models.role import SystemRole
from models.user import SystemUser, SystemUserRole
from utils.pagination import PageParams, get_page_params, paginate
from utils.response import ResponseUtil

roleAPI = APIRouter(prefix="/role", tags=["role"])


def build_policy_payload(permission: dict) -> dict:
    menu_type = permission.get("menu_type")
    permission_id = str(permission.get("id"))

    if menu_type == 0:
        return {
            "permission_key": permission_id,
            "v1": permission_id,
            "v2": "menu",
        }

    if menu_type == 1:
        return {
            "permission_key": permission_id,
            "v1": permission_id,
            "v2": "button",
        }

    api_path = permission.get("api_path") or permission_id
    api_method = permission.get("api_method")
    if isinstance(api_method, list):
        api_method_value = api_method[0] if api_method else "GET"
    else:
        api_method_value = api_method or "GET"

    return {
        "permission_key": permission_id,
        "v1": str(api_path),
        "v2": str(api_method_value).upper(),
    }


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
        current_role = await SystemRole.filter(id=role.id, is_del=False).first()
        if not current_role:
            return ResponseUtil.failure(msg="角色不存在")

        bindings = await SystemUserRole.filter(role_id=role.id, is_del=False).values("user_id")
        if bindings:
            user_ids = [item["user_id"] for item in bindings if item.get("user_id")]
            users = await SystemUser.filter(id__in=user_ids, is_del=False).values("username", "nickname")

            user_names = []
            for user in users[:10]:
                display_name = user.get("username") or user.get("nickname") or ""
                if display_name:
                    user_names.append(display_name)

            suffix = " 等" if len(users) > 10 else ""
            return ResponseUtil.failure(
                msg=f"该角色下仍绑定了 {len(users)} 个用户，无法删除",
                data={
                    "role_id": role.id,
                    "role_name": current_role.name,
                    "bound_user_count": len(users),
                    "bound_users": user_names,
                    "detail": f"请先移除这些用户的角色绑定：{'、'.join(user_names)}{suffix}",
                },
            )

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

    target_permission_ids = [
        str(permission_id)
        for permission_id in dict.fromkeys(payload.permission_ids)
        if permission_id is not None
    ]

    permission_rows = await SystemPermission.filter(
        id__in=target_permission_ids,
        is_del=False,
    ).values("id", "menu_type", "api_path", "api_method")
    permission_payload_map = {
        item["permission_key"]: item
        for item in (build_policy_payload(row) for row in permission_rows)
    }
    valid_permission_ids = [permission_id for permission_id in target_permission_ids if permission_id in permission_payload_map]

    existing_rules = await CasbinRule.filter(v0=role.code).order_by("created_at").all()
    rules_by_permission_id = {}
    for rule in existing_rules:
        if rule.v1:
            matched_permission_id = None
            for permission_id, policy in permission_payload_map.items():
                if str(rule.v1) == str(policy["v1"]):
                    matched_permission_id = permission_id
                    break
            if matched_permission_id is None:
                matched_permission_id = str(rule.v1)
            rules_by_permission_id.setdefault(matched_permission_id, []).append(rule)

    for permission_id, rules in rules_by_permission_id.items():
        primary_rule = rules[0]
        duplicate_rules = rules[1:]

        for duplicate_rule in duplicate_rules:
            if not duplicate_rule.is_del:
                await CasbinRule.filter(id=duplicate_rule.id).update(is_del=True)

        if permission_id in valid_permission_ids:
            policy = permission_payload_map.get(permission_id)
            update_data = {"is_del": False}
            if policy:
                update_data["v1"] = policy["v1"]
                update_data["v2"] = policy["v2"]
            if primary_rule.is_del:
                await CasbinRule.filter(id=primary_rule.id).update(**update_data)
            elif policy and (primary_rule.v1 != policy["v1"] or primary_rule.v2 != policy["v2"]):
                await CasbinRule.filter(id=primary_rule.id).update(v1=policy["v1"], v2=policy["v2"])
        elif not primary_rule.is_del:
            await CasbinRule.filter(id=primary_rule.id).update(is_del=True)

    new_permission_ids = [
        permission_id
        for permission_id in valid_permission_ids
        if permission_id not in rules_by_permission_id
    ]
    if new_permission_ids:
        await CasbinRule.bulk_create(
            [
                CasbinRule(
                    ptype="p",
                    v0=role.code,
                    v1=permission_payload_map[permission_id]["v1"],
                    v2=permission_payload_map[permission_id]["v2"],
                    is_del=False,
                )
                for permission_id in new_permission_ids
            ]
        )

    return ResponseUtil.success()
