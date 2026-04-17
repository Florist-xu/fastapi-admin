from fastapi import APIRouter, Request

from fields.user import RefreshTokenIn, UserLogin
from models.user import SystemUser
from utils.access_context import get_user_access_context
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
        return ResponseUtil.unauthorized(msg="用户不存在或已被禁用")

    access_context = await get_user_access_context(str(user.id))
    info_data = {
        "id": str(user.id),
        "userId": str(user.id),
        "username": user.username,
        "nickname": user.nickname,
        "email": user.email,
        "phone": user.phone,
        "avatar": user.avatar,
        "gender": user.gender,
        "status": user.status,
        "user_type": user.user_type,
        **access_context,
    }
    return ResponseUtil.success(data=info_data)


@authAPI.post("/login")
async def login(loginInfo: UserLogin, request: Request):
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

    await create_login_notification(user, request)
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
        return ResponseUtil.unauthorized(msg="用户不存在或已被禁用")

    data = create_token_pair(user_id=str(user.id), username=user.username)
    return ResponseUtil.success(data=data)
