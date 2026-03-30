from fastapi import FastAPI

from .auth import authAPI
from .casbin import casbinAPI
from .department import departmentAPI
from .role import roleAPI
from .sql import sqlAPI
from .user import userAPI
from .permission import permissionAPI


ROUTERS = (
    userAPI,
    authAPI,
    sqlAPI,
    roleAPI,
    casbinAPI,
    departmentAPI,
    permissionAPI
)


def register_routers(app: FastAPI) -> None:
    for router in ROUTERS:
        app.include_router(router=router)


__all__ = [
    "authAPI",
    "casbinAPI",
    "departmentAPI",
    "roleAPI",
    "sqlAPI",
    "userAPI",
    "ROUTERS",
    'permissionAPI',
    "register_routers",
]
