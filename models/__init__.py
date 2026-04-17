from models.role import SystemRole
from models.user import SystemUser, SystemUserRole
from models.department import SystemDepartment
from models.casbin_rule import CasbinRule
from models.menus import SystemPermission
from models.operation_log import SystemOperationLog
from models.article import SystemArticle
from models.article_meta import SystemArticleCategory, SystemArticleTag
from models.runtime_module import SystemRuntimeModule
from models.notification import SystemNotification, SystemUserNotification
from models.scheduled_action import SystemScheduledAction, SystemScheduledClientEvent
from models.dashboard import (
    SystemDashboardRoleTemplate,
    SystemDashboardTemplate,
    SystemDashboardUserConfig,
)
from models.fishtank import SystemFishTank, SystemFishTankRecord, SystemFishTankSpecies


__all__ = [
    "SystemRole",
    "SystemUser",
    "SystemDepartment",
    "SystemPermission",
    "CasbinRule",
    "SystemUserRole",
    "SystemOperationLog",
    "SystemArticle",
    "SystemArticleCategory",
    "SystemArticleTag",
    "SystemRuntimeModule",
    "SystemNotification",
    "SystemUserNotification",
    "SystemScheduledAction",
    "SystemScheduledClientEvent",
    "SystemDashboardTemplate",
    "SystemDashboardRoleTemplate",
    "SystemDashboardUserConfig",
    "SystemFishTank",
    "SystemFishTankRecord",
    "SystemFishTankSpecies",
]
