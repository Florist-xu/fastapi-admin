from fastapi import APIRouter, Depends
from utils.response import ResponseUtil
from utils.pagination import get_page_params, paginate, PageParams
from  models.user import SystemUser
from fields.user import UserCreate, UserOut, UserUpdate,deleteUser
from utils.security import hash_password

userAPI = APIRouter(prefix="/user", tags=["user"])




@userAPI.get("/list",summary="所有用户") 
async def get_user_list(page: PageParams = Depends(get_page_params)): 
    data = await paginate(SystemUser.all().filter(is_del=False), page.current, page.size)
    return ResponseUtil.success(
        data=data
    )



@userAPI.post("/add",summary="增加")
async def add(addInfo: UserCreate):
    exists = await SystemUser.filter(username__iexact=addInfo.username, is_del=False).exists()
    if exists:
        return ResponseUtil.failure(msg="用户名已存在")
    create_data = addInfo.model_dump()
    create_data["password"] = hash_password(addInfo.password)
    


    await SystemUser.create(**create_data)
    return ResponseUtil.success(msg="添加成功")


@userAPI.post("/update",summary="修改")
async def update(updateInfo: UserUpdate):
    update_data = updateInfo.model_dump(exclude={"id"}, exclude_none=True)
    if "password" in update_data and update_data["password"]:
        update_data["password"] = hash_password(update_data["password"])
    await SystemUser.filter(id=updateInfo.id).update(**update_data)
    fields = list(UserOut.model_fields.keys())
    data = await SystemUser.filter(id=updateInfo.id).values(*fields)
    user_out = UserOut(**(data[0] if data else updateInfo.model_dump()))
    return ResponseUtil.success(
            data=user_out.model_dump()
        )

@userAPI.post("/delete",summary="删除")
async def delete(deleteInfo: deleteUser):
    user = await SystemUser.filter(id=deleteInfo.id).update(is_del=True)
    return ResponseUtil.success(
            data=user
        )
