from fastapi import APIRouter,Depends
from models.menus import SystemPermission
from utils.response import ResponseUtil
from utils.pagination import get_page_params, paginate, PageParams

casbinAPI = APIRouter(prefix="/menus", tags=["权限配置"])

@casbinAPI.get("/list", summary="获取角色列表")
async def menus(page: PageParams = Depends(get_page_params)):
    menu_list = SystemPermission.filter(is_del=False)
    data = await paginate(menu_list, page.current, page.size)
    
    return ResponseUtil.success(data=data)


# 删除菜单权限
@casbinAPI.delete("/delete/{id}", summary="删除菜单权限")
async def delete_menu(id: str):
    try:
        await SystemPermission.filter(id=id).update(is_del=True)
        return ResponseUtil.success()
    except Exception:
        return ResponseUtil.error(msg="删除失败")