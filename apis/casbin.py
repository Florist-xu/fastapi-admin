from fastapi import APIRouter, Depends

from models.menus import SystemPermission
from utils.pagination import PageParams, get_page_params, paginate
from utils.response import ResponseUtil


casbinAPI = APIRouter(prefix="/casbin", tags=["casbin"])


@casbinAPI.get("/menus/list", summary="获取权限配置列表")
async def menus(page: PageParams = Depends(get_page_params)):
    menu_list = SystemPermission.filter(is_del=False)
    data = await paginate(menu_list, page.current, page.size)
    return ResponseUtil.success(data=data)


@casbinAPI.delete("/menus/delete/{id}", summary="删除菜单权限配置")
async def delete_menu(id: str):
    try:
        await SystemPermission.filter(id=id).update(is_del=True)
        return ResponseUtil.success()
    except Exception:
        return ResponseUtil.error(msg="删除失败")
