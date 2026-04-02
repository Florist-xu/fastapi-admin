from fastapi import FastAPI

from .ai import aiAPI
from .auth import authAPI
from .casbin import casbinAPI
from .department import departmentAPI
from .menus import menusAPI
from .operation_log import operationLogAPI
from .role import roleAPI
from .sql import sqlAPI
from .user import userAPI
from .permission import permissionAPI


ROUTERS = (
    userAPI,
    authAPI,
    aiAPI,
    operationLogAPI,
    sqlAPI,
    roleAPI,
    casbinAPI,
    departmentAPI,
    menusAPI,
    permissionAPI
)


def register_routers(app: FastAPI) -> None:
    for router in ROUTERS:
        app.include_router(router=router)


__all__ = [
    "aiAPI",
    "authAPI",
    "casbinAPI",
    "departmentAPI",
    "menusAPI",
    "operationLogAPI",
    "roleAPI",
    "sqlAPI",
    "userAPI",
    "ROUTERS",
    'permissionAPI',
    "register_routers",
]
