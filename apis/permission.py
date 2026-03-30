from fastapi import APIRouter
from models.menus import SystemPermission
from utils.response import ResponseUtil



permissionAPI = APIRouter(prefix="/permission", tags=["权限管理"])

@permissionAPI.get("/list", summary="权限列表")
async def menus():
    menu_list = await SystemPermission.filter(is_del=False)
    
    return ResponseUtil.success(data=menu_list)

# 