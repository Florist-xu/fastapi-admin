from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from tortoise import Tortoise, connections
from tortoise.contrib.fastapi import register_tortoise

from apis import register_routers
from config import TORTOISE_ORM
from middlewares import setup_middlewares
from utils.article_bootstrap import ensure_article_permissions
from utils.article_schema import ensure_article_taxonomy_schema
from utils.dashboard_bootstrap import ensure_dashboard_permissions
from utils.dashboard_schema import ensure_dashboard_schema
from utils.form_designer_bootstrap import ensure_form_designer_permissions
from utils.fishtank_schema import ensure_fishtank_schema
from utils.fishtank_seed import ensure_fishtank_seed_data
from utils.fishtank_bootstrap import ensure_fishtank_permissions
from utils.module_bootstrap import ensure_runtime_module_permissions
from utils.module_manager import runtime_module_manager
from utils.module_schema import ensure_runtime_module_schema
from utils.notification_bootstrap import ensure_notification_permissions
from utils.notification_schema import ensure_notification_schema
from utils.scheduled_action_runner import ensure_scheduled_action_runner, shutdown_scheduled_action_runner
from utils.scheduled_action_schema import ensure_scheduled_action_schema
from utils.response import HttpStatusConstant, ResponseUtil


app = FastAPI()
upload_dir = Path(__file__).resolve().parent / "uplode"
upload_dir.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_tortoise(app, config=TORTOISE_ORM, generate_schemas=False)
setup_middlewares(app)
app.mount("/files", StaticFiles(directory=str(upload_dir)), name="files")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        errors.append({"字段": loc, "message": msg})

    return ResponseUtil.failure(
        code=HttpStatusConstant.BAD_REQUEST,
        msg="参数校验失败",
        data={"errors": errors},
    )


register_routers(app)


async def should_bootstrap_orm_schema() -> bool:
    connection = connections.get("default")
    rows = await connection.execute_query_dict("SHOW TABLES LIKE 'system_user'")
    return not rows


@app.on_event("startup")
async def startup_init_article_module():
    if await should_bootstrap_orm_schema():
        await Tortoise.generate_schemas(safe=True)
    await ensure_article_taxonomy_schema()
    await ensure_runtime_module_schema()
    await ensure_notification_schema()
    await ensure_scheduled_action_schema()
    await ensure_dashboard_schema()
    await ensure_fishtank_schema()
    await ensure_article_permissions()
    await ensure_dashboard_permissions()
    await ensure_form_designer_permissions()
    await ensure_fishtank_permissions()
    await ensure_runtime_module_permissions()
    await ensure_notification_permissions()
    await ensure_fishtank_seed_data()
    await runtime_module_manager.initialize()
    ensure_scheduled_action_runner()


@app.on_event("shutdown")
async def shutdown_runtime_services():
    await shutdown_scheduled_action_runner()
