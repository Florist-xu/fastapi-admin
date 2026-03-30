from fastapi import APIRouter, Depends, Query
from typing import List, Dict
from tortoise.expressions import Q
from utils.response import ResponseUtil
from utils.pagination import get_page_params, paginate, PageParams
from models.user import SystemUser, SystemUserRole
from models.department import SystemDepartment
from models.role import SystemRole
from models.casbin_rule import CasbinRule
from models.menus import SystemPermission
from fields.user import UserCreate, UserRoleUpdate, UserUpdate
from utils.security import hash_password

userAPI = APIRouter(prefix="/user", tags=["user"])


@userAPI.get("/list", summary="所有用户")
async def get_user_list(department_ids: str = Query(None), page: PageParams = Depends(get_page_params)):
    query = SystemUser.filter(is_del=False)
    if department_ids:
        department_id_list = [item.strip() for item in department_ids.split(",") if item.strip()]
        if department_id_list:
            query = query.filter(department_id__in=department_id_list)

    data = await paginate(query, page.current, page.size)
    for i in range(len(data["records"])):
            item = data["records"][i]
            item_dict = dict(item)

            # 获取部门名称
            dept = await SystemDepartment.filter(id=item.department_id).first()
            item_dict["department_name"] = dept.name if dept else ""

            data["records"][i] = item_dict

    return ResponseUtil.success(data=data)


@userAPI.post("/add", summary="增加")
async def add(addInfo: UserCreate):
    exists = await SystemUser.filter(username__iexact=addInfo.username, is_del=False).exists()
    if exists:
        return ResponseUtil.failure(msg="用户名已存在")
    create_data = addInfo.model_dump()
    create_data["password"] = hash_password(addInfo.password)

    await SystemUser.create(**create_data)
    return ResponseUtil.success(msg="添加成功")


@userAPI.post("/update/{id}", summary="修改")
async def update(id:str,updateInfo: UserUpdate):
    update_data = updateInfo.model_dump(exclude_none=True)
    if "password" in update_data and update_data["password"]:
        update_data["password"] = hash_password(update_data["password"])
    await SystemUser.filter(id=id).update(**update_data)
    return ResponseUtil.success(msg="修改成功")


@userAPI.get("/delete/{id}", summary="删除")
async def delete(id:str):
    user = await SystemUser.filter(id=id).update(is_del=True)
    return ResponseUtil.success(msg="删除成功")


# y用户角色列表
@userAPI.get("/roleList/{user_id}", summary="用户角色列表")
async def get_user_role_list(user_id):
    roles = await SystemUserRole.filter(user_id=user_id, is_del=False).all()
    if roles:
        role_ids = []
        for i in range(len(roles)):
            if roles[i].role_id:
                role_ids.append(str(roles[i].role_id))

        role_list = await SystemRole.filter(id__in=role_ids).values("id", "name", "code")
        return ResponseUtil.success(data=role_list)

    return ResponseUtil.error(msg="用户角色不存在")


# 用户角色修改
@userAPI.post("/addRole", summary="用户角色修改")
async def add_user_role(payload: UserRoleUpdate):
    user = await SystemUser.filter(id=payload.user_id, is_del=False).first()
    if not user:
        return ResponseUtil.error(msg="用户不存在")

    # 去重后保留本次目标角色
    role_ids = [role_id for role_id in dict.fromkeys(payload.role_ids) if role_id]

    role_rows = await SystemRole.filter(id__in=role_ids, is_del=False).values_list("id", flat=True)
    valid_role_ids = {str(role_id) for role_id in role_rows if role_id}
    if role_ids and not valid_role_ids:
        return ResponseUtil.error(msg="角色不存在")

    # 查询用户全部历史角色记录，包含已软删数据，后续优先复用旧记录
    existing_relations = await SystemUserRole.filter(user_id=payload.user_id).order_by("created_at").all()
    relations_by_role_id = {}
    for relation in existing_relations:
        if relation.role_id:
            relations_by_role_id.setdefault(str(relation.role_id), []).append(relation)

    for role_id, relations in relations_by_role_id.items():
        # 同一角色如果历史上有多条，只保留最早一条作为主记录，其余重复项软删
        primary_relation = relations[0]
        duplicate_relations = relations[1:]

        for duplicate_relation in duplicate_relations:
            if not duplicate_relation.is_del:
                await SystemUserRole.filter(id=duplicate_relation.id).update(is_del=True)

        # 本次仍然选中的角色直接恢复；取消勾选的角色执行软删
        if role_id in valid_role_ids:
            if primary_relation.is_del:
                await SystemUserRole.filter(id=primary_relation.id).update(is_del=False)
        elif not primary_relation.is_del:
            await SystemUserRole.filter(id=primary_relation.id).update(is_del=True)

    # 只有数据库里从未出现过的角色才真正新建
    new_role_ids = [role_id for role_id in valid_role_ids if role_id not in relations_by_role_id]
    if new_role_ids:
        await SystemUserRole.bulk_create(
            [SystemUserRole(user_id=payload.user_id, role_id=role_id) for role_id in new_role_ids]
        )

    return ResponseUtil.success(msg="用户角色修改成功")



# 密码重置
@userAPI.post("/resetPassword/{id}", summary="密码重置")
async def reset_password(id: str,password: str=Query("123456", description="密码")):
    await SystemUser.filter(id=id).update(password=hash_password(password))
    return ResponseUtil.success(msg="密码重置成功")



# 用户权限详情
@userAPI.get("/permissionsList/{user_id}", summary="用户权限详情")
async def get_user_permissions_list(user_id: str):
    """
    获取用户权限详情：角色 + 菜单 + 按钮 + API
    """
    # 1. 校验用户是否存在
    user = await SystemUser.filter(id=user_id, is_del=False).first()
    if not user:
        return ResponseUtil.error(msg="用户不存在")

    # 2. 获取用户角色
    role_ids = await SystemUserRole.filter(
        user_id=user_id, is_del=False
    ).values_list("role_id", flat=True)

    if not role_ids:
        return ResponseUtil.error(msg="用户未分配角色")

    # 3. 获取角色信息（code、id、name）
    role_rows = await SystemRole.filter(
        id__in=role_ids, is_del=False
    ).values("id", "code", "name")

    if not role_rows:
        return ResponseUtil.error(msg="角色信息不存在")

    # 构建角色映射表
    role_codes = [row["code"] for row in role_rows if row.get("code")]
    role_id_map = {row["code"]: str(row["id"]) for row in role_rows}
    role_name_map = {row["code"]: row["name"] for row in role_rows}

    # 4. 获取 Casbin 权限规则
    permissions = await CasbinRule.filter(v0__in=role_codes, is_del=False).all()
    if not permissions:
        return ResponseUtil.error(msg="用户权限不存在")

    # 5. 构建权限映射表
    permission_map = await build_permission_map(permissions)

    # 6. 解析权限列表（菜单/按钮/API）
    apis, buttons, menus, result = parse_permissions(
        permissions, permission_map, role_id_map, role_name_map
    )

    # 7. 返回结果
    return ResponseUtil.success(data={
        "apis": apis,
        "buttons": buttons,
        "menus": menus,
        "result": result,
        "roles": role_codes,
    })


async def build_permission_map(permissions: List[CasbinRule]) -> Dict[str, Dict]:
    """
    构建权限映射表：id / path / api_path / authMark → 权限详情
    """
    # 收集所有权限唯一标识
    v1_set = {p.v1 for p in permissions if p.v1}
    if not v1_set:
        return {}

    # 批量查询权限
    permission_rows = await SystemPermission.filter(is_del=False).filter(
        Q(id__in=v1_set) | Q(api_path__in=v1_set)
    ).values(
        "id", "parent_id", "menu_type", "authMark",
        "name", "title", "authTitle", "path", "api_path", "api_method"
    )

    # 构建多键映射（一个权限可通过多种 key 获取）
    permission_map = {}
    for row in permission_rows:
        keys = [row.get("id"), row.get("path"), row.get("api_path"), row.get("authMark")]
        for key in filter(None, keys):
            permission_map[str(key)] = row

    return permission_map


def parse_permissions(
    permissions: List[CasbinRule],
    permission_map: Dict[str, Dict],
    role_id_map: Dict[str, str],
    role_name_map: Dict[str, str]
):
    """
    解析权限，分类为 API、按钮、菜单
    最终排序：菜单 → 按钮 → API
    """
    api_set = set()
    menu_items = []   # 存放所有菜单
    button_items = [] # 存放所有按钮
    api_items = []    # 存放所有API
    menus = []
    buttons = []

    for perm in permissions:
        v0, v1, v2 = perm.v0 or "", perm.v1 or "", perm.v2 or ""
        perm_row = permission_map.get(v1, {})

        # 权限名称
        perm_name = (
            perm_row.get("authTitle")
            or perm_row.get("title")
            or perm_row.get("name")
            or v1
        )

        # 构建权限项
        item = {
            "permission_id": perm_row.get("id") or v1,
            "parent_id": perm_row.get("parent_id"),
            "perm_type": "",
            "permission_name": perm_name,
            "permission_type": perm_row.get("menu_type"),
            "role_id": role_id_map.get(v0),
            "role_name": role_name_map.get(v0),
        }

        # 判断类型并分类
        if v2.startswith("button"):
            item["perm_type"] = "button"
            item["permission_auth"] = perm_row.get("authMark")
            button_items.append(item)
            buttons.append(v1)

        elif v2.startswith("menu"):
            item["perm_type"] = "menu"
            menu_items.append(item)
            menus.append(v1)

        else:
            item["perm_type"] = "api"
            item["api_method"] = v2
            item["api_path"] = perm_row.get("api_path") or v1
            api_items.append(item)
            api_set.add(f"[{v2}]:{v1}")

    # ✅ 最终合并顺序：菜单 → 按钮 → API
    result = menu_items + button_items + api_items
    apis = list(api_set)

    return apis, buttons, menus, result
