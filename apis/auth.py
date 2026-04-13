from fastapi import APIRouter, Request
from tortoise.expressions import Q

from fields.user import RefreshTokenIn, UserLogin
from models.casbin_rule import CasbinRule
from models.menus import SystemPermission
from models.role import SystemRole
from models.user import SystemUser, SystemUserRole
from utils.notification_service import create_login_notification
from utils.response import ResponseUtil
from utils.security import hash_password, verify_password
from utils.token import create_token_pair, verify_jwt

authAPI = APIRouter(prefix="/auth", tags=["auth"])


@authAPI.get("/info")
async def create_user(request: Request):
    payload = getattr(request.state, "user", {}) or {}
    user_id = payload.get("sub")
    if not user_id:
        return ResponseUtil.unauthorized(msg="未登录或登录已过期")

    user = await SystemUser.filter(id=user_id, is_del=False).first()
    if not user:
        return ResponseUtil.unauthorized(msg="用户不存在或已禁用")

    role_ids = await SystemUserRole.filter(
        user_id=user.id,
        is_del=False,
    ).values_list("role_id", flat=True)
    role_ids = [rid for rid in role_ids if rid]

    roles = []
    buttons = []
    if role_ids:
        role_rows = await SystemRole.filter(
            id__in=role_ids,
            is_del=False,
        ).values("code")
        roles = [row["code"] for row in role_rows if row.get("code")]

        if roles:
            permission_refs = await CasbinRule.filter(
                is_del=False,
                ptype="p",
                v0__in=roles,
                v2="button",
            ).values_list("v1", flat=True)
            permission_refs = list({ref for ref in permission_refs if ref})

            if permission_refs:
                permission_rows = await SystemPermission.filter(is_del=False).filter(
                    Q(id__in=permission_refs)
                    | Q(path__in=permission_refs)
                    | Q(api_path__in=permission_refs)
                ).values("authMark", "id", "path", "api_path")
                button_codes = []
                for row in permission_rows:
                    code = row.get("authMark") or row.get("id") or row.get("path") or row.get("api_path")
                    if code:
                        button_codes.append(code)
                buttons = list(dict.fromkeys(button_codes))

    info_data = {
        "userId": str(user.id),
        "username": user.username,
        "roles": list(dict.fromkeys(roles)),
        "permission_marks": buttons,
        "email": user.email,
        "user_type": user.user_type,
    }
    return ResponseUtil.success(data=info_data)


@authAPI.post("/login")
async def login(loginInfo: UserLogin):
    login_username = loginInfo.username.strip()
    users = await SystemUser.filter(
        username__iexact=login_username,
        is_del=False,
    ).order_by("-created_at")
    if len(users) > 1:
        return ResponseUtil.failure(msg="存在重名用户，请联系管理员清理重复账号")
    user = users[0] if users else None
    if not user:
        return ResponseUtil.failure(msg="用户不存在")

    if verify_password(loginInfo.password, user.password):
        pass
    elif user.password == loginInfo.password:
        new_password = hash_password(loginInfo.password)
        await SystemUser.filter(id=user.id).update(password=new_password)
    else:
        return ResponseUtil.failure(msg="密码错误")

    await create_login_notification(user)
    data = create_token_pair(user_id=str(user.id), username=user.username)
    return ResponseUtil.success(data=data)


@authAPI.post("/refresh")
async def refresh_token(refreshInfo: RefreshTokenIn):
    payload = verify_jwt(refreshInfo.refreshToken, token_type="refresh")
    if not payload:
        return ResponseUtil.unauthorized(msg="refreshToken无效或已过期")

    user_id = payload.get("sub")
    username = payload.get("username")
    if not user_id or not username:
        return ResponseUtil.unauthorized(msg="refreshToken无效或已过期")

    user = await SystemUser.filter(id=user_id, is_del=False).first()
    if not user:
        return ResponseUtil.unauthorized(msg="用户不存在或已禁用")

    data = create_token_pair(user_id=str(user.id), username=user.username)
    return ResponseUtil.success(data=data)
