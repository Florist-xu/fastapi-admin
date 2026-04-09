from fastapi import Request

from utils.response import ResponseUtil
from utils.token import verify_jwt

PUBLIC_PATHS = {
    "/auth/login",
    "/auth/refresh",
    "/casbin/menus",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
}


async def auth_middleware(request: Request, call_next):
    if (
        request.method == "OPTIONS"
        or request.url.path in PUBLIC_PATHS
        or request.url.path.startswith("/files/")
    ):
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "").strip()
    if not auth_header:
        return ResponseUtil.unauthorized(msg="未登录或登录已过期")

    token = ""
    lower_header = auth_header.lower()
    if lower_header.startswith("bearer "):
        token = auth_header[7:].strip()
    elif lower_header.startswith("bearer"):
        token = auth_header[6:].strip()

    if not token:
        return ResponseUtil.unauthorized(msg="未登录或登录已过期")

    payload = verify_jwt(token, token_type="access")
    if not payload:
        return ResponseUtil.unauthorized(msg="未登录或登录已过期")

    request.state.user = payload
    return await call_next(request)
