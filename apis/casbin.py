from fastapi import APIRouter
from models.casbin_rule import CasbinRule
from models.menus import System_permission
from utils.response import ResponseUtil



casbinAPI = APIRouter(prefix="/casbin", tags=["权限配置"])

@casbinAPI.get("/menus", summary="获取角色列表")
async def menus():
    menu_list = await CasbinRule.all().filter(v2="menu")
    
    return ResponseUtil.success(data=menu_list)
    # menus  =await  System_permission.all().filter(menu_type=0)
    # for menu in menu_list:
    # return ResponseUtil.success(data=menu_list)