from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise

from apis.auth import authAPI
from apis.role import roleAPI
from apis.sql import sqlAPI
from apis.user import userAPI
from apis.casbin import casbinAPI
from config import TORTOISE_ORM
from middlewares import setup_middlewares
from utils.response import ResponseUtil, HttpStatusConstant


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_tortoise(app, config=TORTOISE_ORM)
setup_middlewares(app)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        errors.append({"field": loc, "message": msg})

    return ResponseUtil.failure(
        code=HttpStatusConstant.BAD_REQUEST,
        msg="参数校验失败",
        data={"errors": errors},
    )


app.include_router(router=userAPI)
app.include_router(router=authAPI)
app.include_router(router=sqlAPI)
app.include_router(router=roleAPI)
app.include_router(router=casbinAPI)
