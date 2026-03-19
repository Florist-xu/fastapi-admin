
from models.role import SystemRole
from models.user import SystemUser, SystemUserRole
from models.department import System_department
from models.casbin_rule import CasbinRule
from models.menus import System_permission



__all__ = [
    'SystemRole',
    'SystemUser',
    'System_department',
    "System_permission",
    'CasbinRule',
    'SystemUserRole']
