from fastapi import FastAPI

from .ai import aiAPI
from .article import articleAPI
from .article_meta import articleCategoryAPI, articleTagAPI
from .auth import authAPI
from .casbin import casbinAPI
from .common import commonAPI
from .dashboard import dashboardAPI
from .department import departmentAPI
from .fishtank import fishtankAPI
from .menus import menusAPI
from .notification import notificationAPI
from .operation_log import operationLogAPI
from .permission import permissionAPI
from .role import roleAPI
from .runtime_module import runtimeModuleAPI
from .scheduled_action import scheduledActionAPI
from .sql import sqlAPI
from .user import userAPI


ROUTERS = (
    userAPI,
    authAPI,
    aiAPI,
    operationLogAPI,
    sqlAPI,
    roleAPI,
    casbinAPI,
    departmentAPI,
    dashboardAPI,
    fishtankAPI,
    menusAPI,
    permissionAPI,
    notificationAPI,
    articleAPI,
    articleCategoryAPI,
    articleTagAPI,
    commonAPI,
    runtimeModuleAPI,
    scheduledActionAPI,
)


def register_routers(app: FastAPI) -> None:
    for router in ROUTERS:
        app.include_router(router=router)


__all__ = [
    "aiAPI",
    "authAPI",
    "casbinAPI",
    "departmentAPI",
    "dashboardAPI",
    "fishtankAPI",
    "menusAPI",
    "notificationAPI",
    "articleAPI",
    "articleCategoryAPI",
    "articleTagAPI",
    "commonAPI",
    "runtimeModuleAPI",
    "scheduledActionAPI",
    "operationLogAPI",
    "roleAPI",
    "sqlAPI",
    "userAPI",
    "permissionAPI",
    "ROUTERS",
    "register_routers",
]
