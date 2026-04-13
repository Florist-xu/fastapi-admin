from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response

from fields.runtime_module import RuntimeModuleConfigUpdate
from utils.module_manager import RuntimeModuleError, runtime_module_manager
from utils.pagination import PageParams, get_page_params
from utils.response import HttpStatusConstant, ResponseUtil


runtimeModuleAPI = APIRouter(prefix="/runtime-module", tags=["runtime-module"])


async def ensure_runtime_manager() -> None:
    await runtime_module_manager.initialize()


@runtimeModuleAPI.get("/list", summary="Runtime module list")
async def list_runtime_modules(
    name: str | None = Query(default=None),
    status: int | None = Query(default=None),
    source_type: str | None = Query(default=None),
    page: PageParams = Depends(get_page_params),
):
    await ensure_runtime_manager()
    rows = await runtime_module_manager.list_modules(name=name, status=status, source_type=source_type)
    total = len(rows)
    start = page.offset
    end = start + page.size
    return ResponseUtil.success(
        data={
            "records": rows[start:end],
            "total": total,
            "current": page.current,
            "size": page.size,
        }
    )


@runtimeModuleAPI.get("/info/{module_code}", summary="Runtime module detail")
async def runtime_module_info(module_code: str):
    await ensure_runtime_manager()
    detail = await runtime_module_manager.get_module_detail(module_code)
    if not detail:
        return ResponseUtil.failure(msg="模块不存在", code=HttpStatusConstant.NOT_FOUND)
    return ResponseUtil.success(data=detail)


@runtimeModuleAPI.get("/examples", summary="Runtime module examples")
async def list_runtime_module_examples():
    await ensure_runtime_manager()
    return ResponseUtil.success(data=runtime_module_manager.list_examples())


@runtimeModuleAPI.get("/client/bootstrap", summary="Runtime module client bootstrap")
async def runtime_module_client_bootstrap():
    await ensure_runtime_manager()
    return ResponseUtil.success(data=await runtime_module_manager.get_client_bootstrap())


@runtimeModuleAPI.get("/client/asset/{module_code}", summary="Runtime module client asset")
async def runtime_module_client_asset(module_code: str, entry: str = Query(...)):
    await ensure_runtime_manager()
    try:
        asset_path = await runtime_module_manager.resolve_client_asset(module_code, entry)
        return FileResponse(asset_path, media_type="text/javascript; charset=utf-8")
    except RuntimeModuleError as exc:
        return ResponseUtil.failure(msg=str(exc), code=HttpStatusConstant.NOT_FOUND)
    except Exception as exc:  # noqa: BLE001
        return ResponseUtil.error(msg=f"模块前端资源读取失败: {exc}")


@runtimeModuleAPI.post("/install/upload", summary="Install module from zip")
async def install_runtime_module_upload(request: Request, file: UploadFile = File(...)):
    await ensure_runtime_manager()
    user = getattr(request.state, "user", {}) or {}
    try:
        result = await runtime_module_manager.install_from_upload(file, user)
        return ResponseUtil.success(msg="模块安装成功", data=result)
    except RuntimeModuleError as exc:
        return ResponseUtil.failure(msg=str(exc))
    except Exception as exc:  # noqa: BLE001
        return ResponseUtil.error(msg=f"模块安装失败: {exc}")


@runtimeModuleAPI.post("/install/example/{example_code}", summary="Install example module")
async def install_runtime_module_example(example_code: str, request: Request):
    await ensure_runtime_manager()
    user = getattr(request.state, "user", {}) or {}
    try:
        result = await runtime_module_manager.install_example(example_code, user)
        return ResponseUtil.success(msg="示例模块安装成功", data=result)
    except RuntimeModuleError as exc:
        return ResponseUtil.failure(msg=str(exc))
    except Exception as exc:  # noqa: BLE001
        return ResponseUtil.error(msg=f"示例模块安装失败: {exc}")


@runtimeModuleAPI.post("/load/{module_code}", summary="Load runtime module")
async def load_runtime_module(module_code: str):
    await ensure_runtime_manager()
    try:
        result = await runtime_module_manager.load_module(module_code)
        return ResponseUtil.success(msg="模块加载成功", data=result)
    except RuntimeModuleError as exc:
        return ResponseUtil.failure(msg=str(exc))
    except Exception as exc:  # noqa: BLE001
        return ResponseUtil.error(msg=f"模块加载失败: {exc}")


@runtimeModuleAPI.post("/unload/{module_code}", summary="Unload runtime module")
async def unload_runtime_module(module_code: str):
    await ensure_runtime_manager()
    try:
        result = await runtime_module_manager.unload_module(module_code)
        return ResponseUtil.success(msg="模块卸载成功", data=result)
    except RuntimeModuleError as exc:
        return ResponseUtil.failure(msg=str(exc))
    except Exception as exc:  # noqa: BLE001
        return ResponseUtil.error(msg=f"模块卸载失败: {exc}")


@runtimeModuleAPI.post("/reload/{module_code}", summary="Reload runtime module")
async def reload_runtime_module(module_code: str):
    await ensure_runtime_manager()
    try:
        result = await runtime_module_manager.reload_module(module_code)
        return ResponseUtil.success(msg="模块重载成功", data=result)
    except RuntimeModuleError as exc:
        return ResponseUtil.failure(msg=str(exc))
    except Exception as exc:  # noqa: BLE001
        return ResponseUtil.error(msg=f"模块重载失败: {exc}")


@runtimeModuleAPI.put("/config/{module_code}", summary="Update runtime module config")
async def update_runtime_module_config(module_code: str, payload: RuntimeModuleConfigUpdate):
    await ensure_runtime_manager()
    try:
        result = await runtime_module_manager.update_config(module_code, payload.config)
        return ResponseUtil.success(msg="模块配置更新成功", data=result)
    except RuntimeModuleError as exc:
        return ResponseUtil.failure(msg=str(exc))
    except Exception as exc:  # noqa: BLE001
        return ResponseUtil.error(msg=f"模块配置更新失败: {exc}")


@runtimeModuleAPI.delete("/uninstall/{module_code}", summary="Uninstall runtime module")
async def uninstall_runtime_module(module_code: str):
    await ensure_runtime_manager()
    try:
        await runtime_module_manager.uninstall_module(module_code)
        return ResponseUtil.success(msg="模块卸载并删除成功")
    except RuntimeModuleError as exc:
        return ResponseUtil.failure(msg=str(exc))
    except Exception as exc:  # noqa: BLE001
        return ResponseUtil.error(msg=f"模块删除失败: {exc}")


@runtimeModuleAPI.api_route(
    "/execute/{module_code}/{route_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    summary="Execute runtime module route",
)
async def execute_runtime_module(module_code: str, route_path: str, request: Request):
    await ensure_runtime_manager()
    try:
        result = await runtime_module_manager.dispatch(module_code, route_path, request)
        if isinstance(result, Response):
            return result
        return ResponseUtil.success(data=result)
    except RuntimeModuleError as exc:
        return ResponseUtil.failure(msg=str(exc), code=HttpStatusConstant.NOT_FOUND)
    except Exception as exc:  # noqa: BLE001
        return ResponseUtil.error(msg=f"模块运行失败: {exc}")
