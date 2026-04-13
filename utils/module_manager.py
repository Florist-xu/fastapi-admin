import asyncio
import importlib
import inspect
import json
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Request, UploadFile

from models.runtime_module import SystemRuntimeModule
from runtime_modules.base import (
    RuntimeModuleBase,
    RuntimeModuleContext,
    RuntimeModuleError,
    RuntimeModuleRoute,
)


MODULE_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{1,99}$")

RUNTIME_MODULE_ROOT = Path(__file__).resolve().parent.parent / "runtime_modules"
RUNTIME_MODULE_PACKAGES = RUNTIME_MODULE_ROOT / "packages"
RUNTIME_MODULE_UPLOADS = RUNTIME_MODULE_ROOT / "_uploads"
RUNTIME_MODULE_EXAMPLES = RUNTIME_MODULE_ROOT / "examples"


@dataclass(slots=True)
class LoadedRuntimeModule:
    record_id: str
    code: str
    module: Any
    instance: RuntimeModuleBase
    routes: dict[tuple[str, str], RuntimeModuleRoute]
    manifest: dict[str, Any]
    install_path: Path


class ResolvedClientManifest(dict[str, list[dict[str, Any]]]):
    routes: list[dict[str, Any]]
    capabilities: list[dict[str, Any]]


class RuntimeModuleManager:
    def __init__(self) -> None:
        self._loaded: dict[str, LoadedRuntimeModule] = {}
        self._init_lock = asyncio.Lock()
        self._initialized = False
        self._revision = datetime.now().isoformat()

    @property
    def revision(self) -> str:
        return self._revision

    def _bump_revision(self) -> None:
        self._revision = datetime.now().isoformat()

    async def initialize(self) -> None:
        async with self._init_lock:
            if self._initialized:
                return

            self._ensure_directories()
            package_root = str(RUNTIME_MODULE_PACKAGES)
            if package_root not in sys.path:
                sys.path.insert(0, package_root)

            records = await SystemRuntimeModule.filter(is_del=False, status=1).values()
            for record in records:
                try:
                    await self.load_module(record["code"], persist_status=False)
                except Exception as exc:  # noqa: BLE001
                    await SystemRuntimeModule.filter(id=record["id"]).update(
                        status=0,
                        route_count=0,
                        last_error=str(exc),
                        last_unloaded_at=datetime.now(),
                    )

            self._initialized = True
            self._bump_revision()

    def _ensure_directories(self) -> None:
        RUNTIME_MODULE_ROOT.mkdir(parents=True, exist_ok=True)
        RUNTIME_MODULE_PACKAGES.mkdir(parents=True, exist_ok=True)
        RUNTIME_MODULE_UPLOADS.mkdir(parents=True, exist_ok=True)
        RUNTIME_MODULE_EXAMPLES.mkdir(parents=True, exist_ok=True)

    def _normalize_entry_module(self, entry_module: str | None) -> str:
        value = (entry_module or "module").strip().replace("\\", ".").replace("/", ".")
        if value.endswith(".py"):
            value = value[:-3]
        return value.strip(".") or "module"

    def _normalize_module_path(self, route_path: str | None) -> str:
        value = (route_path or "").strip()
        if not value or value == "/":
            return "/"
        return "/" + value.strip("/")

    def _normalize_asset_entry(self, value: str | None) -> str:
        entry = str(value or "").strip().replace("\\", "/").lstrip("/")
        if not entry:
            raise RuntimeModuleError("Frontend route entry is required")
        if ".." in Path(entry).parts:
            raise RuntimeModuleError("Frontend route entry contains invalid path traversal")
        if Path(entry).suffix.lower() not in {".js", ".mjs"}:
            raise RuntimeModuleError("Frontend route entry must be a .js or .mjs file")
        return entry

    def _normalize_string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _normalize_client_route(self, module_code: str, index: int, route: dict[str, Any]) -> dict[str, Any]:
        title = str(route.get("title") or "").strip()
        if not title:
            raise RuntimeModuleError("Frontend route title is required")

        path = str(route.get("path") or "").strip().strip("/")
        if not path:
            raise RuntimeModuleError("Frontend route path is required")

        name = str(route.get("name") or f"RuntimeModule{module_code.title()}Route{index + 1}").strip()
        if not name:
            raise RuntimeModuleError("Frontend route name is required")

        props = route.get("props") if isinstance(route.get("props"), dict) else {}
        return {
            "path": path,
            "name": name,
            "title": title,
            "entry": self._normalize_asset_entry(route.get("entry")),
            "parent_path": str(route.get("parent_path") or route.get("parentPath") or "").strip()
            or None,
            "icon": str(route.get("icon") or "").strip() or None,
            "order": int(route.get("order") or 999),
            "keep_alive": bool(route.get("keep_alive") if "keep_alive" in route else route.get("keepAlive")),
            "is_hide": bool(route.get("is_hide") if "is_hide" in route else route.get("isHide")),
            "is_hide_tab": bool(
                route.get("is_hide_tab") if "is_hide_tab" in route else route.get("isHideTab")
            ),
            "fixed_tab": bool(route.get("fixed_tab") if "fixed_tab" in route else route.get("fixedTab")),
            "active_path": str(route.get("active_path") or route.get("activePath") or "").strip() or None,
            "is_full_page": bool(
                route.get("is_full_page") if "is_full_page" in route else route.get("isFullPage")
            ),
            "min_user_type": int(route.get("min_user_type") or route.get("minUserType") or 3),
            "roles": self._normalize_string_list(route.get("roles")),
            "auth": self._normalize_string_list(route.get("auth")),
            "export_name": str(route.get("export_name") or route.get("exportName") or "default").strip()
            or "default",
            "props": props,
        }

    def _normalize_capability(self, capability: dict[str, Any]) -> dict[str, Any]:
        key = str(capability.get("key") or "").strip()
        if not key:
            raise RuntimeModuleError("Capability key is required")

        endpoint = capability.get("endpoint")
        normalized_endpoint = self._normalize_module_path(endpoint) if endpoint else None
        config = capability.get("config") if isinstance(capability.get("config"), dict) else {}
        return {
            "key": key,
            "title": str(capability.get("title") or key).strip() or key,
            "endpoint": normalized_endpoint,
            "order": int(capability.get("order") or 999),
            "min_user_type": int(capability.get("min_user_type") or capability.get("minUserType") or 3),
            "roles": self._normalize_string_list(capability.get("roles")),
            "auth": self._normalize_string_list(capability.get("auth")),
            "config": config,
        }

    def _normalize_frontend_manifest(
        self, module_code: str, manifest: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        frontend_value = manifest.get("frontend")
        frontend: dict[str, Any] = frontend_value if isinstance(frontend_value, dict) else {}

        routes_value = frontend.get("routes")
        raw_routes: list[Any] = routes_value if isinstance(routes_value, list) else []

        capabilities_value = frontend.get("capabilities")
        raw_capabilities: list[Any] = capabilities_value if isinstance(capabilities_value, list) else []

        routes = [
            self._normalize_client_route(module_code, index, item)
            for index, item in enumerate(raw_routes)
            if isinstance(item, dict)
        ]
        capabilities = [
            self._normalize_capability(item) for item in raw_capabilities if isinstance(item, dict)
        ]
        return routes, capabilities

    def _resolve_client_manifest(
        self, module_code: str, manifest: dict[str, Any] | None
    ) -> ResolvedClientManifest:
        data = manifest if isinstance(manifest, dict) else {}
        frontend_value = data.get("frontend")
        frontend: dict[str, Any] = frontend_value if isinstance(frontend_value, dict) else {}

        routes_value = frontend.get("routes")
        routes: list[Any] = routes_value if isinstance(routes_value, list) else []

        capabilities_value = frontend.get("capabilities")
        capabilities: list[Any] = capabilities_value if isinstance(capabilities_value, list) else []

        return ResolvedClientManifest({
            "routes": [item for item in routes if isinstance(item, dict)],
            "capabilities": [
                {
                    **item,
                    "module_code": module_code,
                }
                for item in capabilities
                if isinstance(item, dict)
            ],
        })

    def _clear_import_cache(self, package_name: str) -> None:
        for module_name in list(sys.modules.keys()):
            if module_name == package_name or module_name.startswith(f"{package_name}."):
                sys.modules.pop(module_name, None)
        importlib.invalidate_caches()

    def _build_context(self, record: dict[str, Any]) -> RuntimeModuleContext:
        return RuntimeModuleContext(
            record_id=str(record["id"]),
            code=record["code"],
            name=record["name"],
            version=record.get("version") or "1.0.0",
            base_dir=Path(record["install_path"]),
            manifest=record.get("manifest") or {},
            config=record.get("config") or {},
        )

    async def _get_record_by_code(self, code: str) -> dict[str, Any] | None:
        rows = await SystemRuntimeModule.filter(code=code, is_del=False).values()
        return rows[0] if rows else None

    async def _require_module_detail(self, code: str) -> dict[str, Any]:
        detail = await self.get_module_detail(code)
        if detail is None:
            raise RuntimeModuleError(f"Module detail does not exist: {code}")
        return detail

    def _build_route_map(self, instance: RuntimeModuleBase) -> dict[tuple[str, str], RuntimeModuleRoute]:
        route_map: dict[tuple[str, str], RuntimeModuleRoute] = {}
        raw_routes = instance.get_routes() or []

        for item in raw_routes:
            route = item if isinstance(item, RuntimeModuleRoute) else RuntimeModuleRoute(**item)
            normalized_path = self._normalize_module_path(route.path)
            methods = [method.upper() for method in route.methods if method]
            if not methods:
                raise RuntimeModuleError(f"Module route {normalized_path} has no methods")

            if not hasattr(instance, route.handler):
                raise RuntimeModuleError(f"Missing handler: {route.handler}")

            for method in methods:
                route_map[(method, normalized_path)] = RuntimeModuleRoute(
                    path=normalized_path,
                    methods=methods,
                    handler=route.handler,
                    summary=route.summary,
                )

        return route_map

    def _load_manifest(self, manifest_root: Path) -> dict[str, Any]:
        manifest_path = manifest_root / "manifest.json"
        if not manifest_path.exists():
            raise RuntimeModuleError("manifest.json is required")

        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeModuleError(f"Invalid manifest.json: {exc}") from exc

    def _validate_manifest(self, manifest: dict[str, Any]) -> dict[str, Any]:
        code = str(manifest.get("code") or "").strip()
        if not MODULE_CODE_RE.match(code):
            raise RuntimeModuleError(
                "Module code must start with a letter and contain only lowercase letters, numbers, and underscores"
            )

        name = str(manifest.get("name") or "").strip()
        if not name:
            raise RuntimeModuleError("Module name is required")

        entry_module = self._normalize_entry_module(manifest.get("entry_module") or manifest.get("entry"))
        class_name = str(manifest.get("class_name") or manifest.get("class") or "Module").strip()
        routes, capabilities = self._normalize_frontend_manifest(code, manifest)
        normalized_manifest = {
            **manifest,
            "frontend": {
                "routes": routes,
                "capabilities": capabilities,
            },
        }

        return {
            "code": code,
            "name": name,
            "version": str(manifest.get("version") or "1.0.0").strip() or "1.0.0",
            "description": str(manifest.get("description") or "").strip() or None,
            "author": str(manifest.get("author") or "").strip() or None,
            "entry_module": entry_module,
            "class_name": class_name or "Module",
            "config": manifest.get("config") or {},
            "manifest": normalized_manifest,
        }

    def _resolve_manifest_root(self, base_dir: Path) -> Path:
        if (base_dir / "manifest.json").exists():
            return base_dir

        manifests = [path.parent for path in base_dir.rglob("manifest.json") if path.is_file()]
        if not manifests:
            raise RuntimeModuleError("manifest.json is missing from uploaded package")
        if len(manifests) > 1:
            raise RuntimeModuleError("Uploaded package contains multiple manifest.json files")
        return manifests[0]

    def _safe_extract_zip(self, archive_path: Path, target_dir: Path) -> None:
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            for member in zip_ref.infolist():
                member_path = (target_dir / member.filename).resolve()
                if target_dir.resolve() not in member_path.parents and member_path != target_dir.resolve():
                    raise RuntimeModuleError("Unsafe zip path detected")
            zip_ref.extractall(target_dir)

    async def install_from_upload(self, file: UploadFile, user: dict[str, Any]) -> dict[str, Any]:
        self._ensure_directories()

        suffix = Path(file.filename or "module.zip").suffix.lower()
        if suffix != ".zip":
            raise RuntimeModuleError("Only zip packages are supported")

        archive_name = f"{uuid4().hex}{suffix}"
        archive_path = RUNTIME_MODULE_UPLOADS / archive_name
        archive_content = await file.read()
        archive_path.write_bytes(archive_content)

        temp_dir = RUNTIME_MODULE_UPLOADS / f"tmp_{uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            self._safe_extract_zip(archive_path, temp_dir)
            manifest_root = self._resolve_manifest_root(temp_dir)
            manifest = self._validate_manifest(self._load_manifest(manifest_root))

            existing = await SystemRuntimeModule.filter(code=manifest["code"], is_del=False).exists()
            if existing:
                raise RuntimeModuleError(f"Module code already exists: {manifest['code']}")

            target_dir = RUNTIME_MODULE_PACKAGES / manifest["code"]
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            shutil.copytree(manifest_root, target_dir)

            init_file = target_dir / "__init__.py"
            if not init_file.exists():
                init_file.write_text('"""Runtime module package."""\n', encoding="utf-8")

            record = await SystemRuntimeModule.create(
                code=manifest["code"],
                name=manifest["name"],
                version=manifest["version"],
                description=manifest["description"],
                author=manifest["author"],
                source_type="upload",
                package_name=manifest["code"],
                entry_module=manifest["entry_module"],
                class_name=manifest["class_name"],
                archive_path=str(archive_path),
                install_path=str(target_dir),
                manifest=manifest["manifest"],
                config=manifest["config"],
                installed_by=user.get("sub"),
                installed_by_name=user.get("username"),
            )

            try:
                loaded = await self.load_module(manifest["code"])
            except Exception as exc:  # noqa: BLE001
                await SystemRuntimeModule.filter(id=record.id).update(last_error=str(exc))
                loaded = await self._require_module_detail(manifest["code"])
            return loaded
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def install_example(self, example_code: str, user: dict[str, Any]) -> dict[str, Any]:
        self._ensure_directories()
        source_dir = RUNTIME_MODULE_EXAMPLES / example_code
        if not source_dir.exists():
            raise RuntimeModuleError("Example module does not exist")

        manifest = self._validate_manifest(self._load_manifest(source_dir))
        existing = await SystemRuntimeModule.filter(code=manifest["code"], is_del=False).exists()
        if existing:
            raise RuntimeModuleError(f"Module code already exists: {manifest['code']}")

        target_dir = RUNTIME_MODULE_PACKAGES / manifest["code"]
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        shutil.copytree(source_dir, target_dir)

        init_file = target_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text('"""Runtime module package."""\n', encoding="utf-8")

        record = await SystemRuntimeModule.create(
            code=manifest["code"],
            name=manifest["name"],
            version=manifest["version"],
            description=manifest["description"],
            author=manifest["author"],
            source_type="example",
            package_name=manifest["code"],
            entry_module=manifest["entry_module"],
            class_name=manifest["class_name"],
            archive_path=None,
            install_path=str(target_dir),
            manifest=manifest["manifest"],
            config=manifest["config"],
            installed_by=user.get("sub"),
            installed_by_name=user.get("username"),
        )

        try:
            return await self.load_module(manifest["code"])
        except Exception as exc:  # noqa: BLE001
            await SystemRuntimeModule.filter(id=record.id).update(last_error=str(exc))
            return await self._require_module_detail(manifest["code"])

    async def load_module(self, code: str, persist_status: bool = True) -> dict[str, Any]:
        record = await self._get_record_by_code(code)
        if not record:
            raise RuntimeModuleError("Module does not exist")

        if code in self._loaded:
            await self.unload_module(code, persist_status=False)

        self._clear_import_cache(record["package_name"])
        import_path = f"{record['package_name']}.{record['entry_module']}"

        try:
            module = importlib.import_module(import_path)
            module_class = getattr(module, record["class_name"], None)
            if module_class is None:
                raise RuntimeModuleError(f"Class {record['class_name']} not found")

            context = self._build_context(record)
            instance = module_class(context)
            if not isinstance(instance, RuntimeModuleBase):
                raise RuntimeModuleError("Module class must inherit RuntimeModuleBase")

            routes = self._build_route_map(instance)
            await instance.on_load()

            self._loaded[code] = LoadedRuntimeModule(
                record_id=str(record["id"]),
                code=code,
                module=module,
                instance=instance,
                routes=routes,
                manifest=record.get("manifest") or {},
                install_path=Path(record["install_path"]),
            )

            if persist_status:
                await SystemRuntimeModule.filter(id=record["id"]).update(
                    status=1,
                    route_count=len(routes),
                    last_loaded_at=datetime.now(),
                    last_error=None,
                )
                self._bump_revision()
        except Exception as exc:  # noqa: BLE001
            self._loaded.pop(code, None)
            if persist_status:
                await SystemRuntimeModule.filter(id=record["id"]).update(
                    status=0,
                    route_count=0,
                    last_error=str(exc),
                    last_unloaded_at=datetime.now(),
                )
                self._bump_revision()
            raise

        return await self._require_module_detail(code)

    async def unload_module(self, code: str, persist_status: bool = True) -> dict[str, Any]:
        loaded = self._loaded.pop(code, None)
        record = await self._get_record_by_code(code)
        if not record:
            raise RuntimeModuleError("Module does not exist")

        if loaded:
            try:
                await loaded.instance.on_unload()
            finally:
                self._clear_import_cache(record["package_name"])

        if persist_status:
            await SystemRuntimeModule.filter(id=record["id"]).update(
                status=0,
                route_count=0,
                last_unloaded_at=datetime.now(),
                last_error=None,
            )
            self._bump_revision()

        return await self._require_module_detail(code)

    async def reload_module(self, code: str) -> dict[str, Any]:
        if code in self._loaded:
            await self.unload_module(code, persist_status=False)
        return await self.load_module(code)

    async def uninstall_module(self, code: str) -> None:
        record = await self._get_record_by_code(code)
        if not record:
            raise RuntimeModuleError("Module does not exist")

        if code in self._loaded:
            await self.unload_module(code, persist_status=False)

        install_path = Path(record["install_path"])
        if install_path.exists():
            shutil.rmtree(install_path, ignore_errors=True)

        archive_path = record.get("archive_path")
        if archive_path:
            Path(archive_path).unlink(missing_ok=True)

        await SystemRuntimeModule.filter(id=record["id"]).delete()
        self._bump_revision()

    async def update_config(self, code: str, config: dict[str, Any]) -> dict[str, Any]:
        record = await self._get_record_by_code(code)
        if not record:
            raise RuntimeModuleError("Module does not exist")

        await SystemRuntimeModule.filter(id=record["id"]).update(config=config)
        loaded = self._loaded.get(code)
        if loaded:
            loaded.instance.context.config = config

        self._bump_revision()
        return await self._require_module_detail(code)

    async def get_module_detail(self, code: str) -> dict[str, Any] | None:
        row = await self._get_record_by_code(code)
        if not row:
            return None

        loaded = self._loaded.get(code)
        routes = []
        if loaded:
            routes = [
                {
                    "method": method,
                    "path": path,
                    "handler": route.handler,
                    "summary": route.summary,
                }
                for (method, path), route in sorted(
                    loaded.routes.items(), key=lambda item: (item[0][1], item[0][0])
                )
            ]

        client_manifest = self._resolve_client_manifest(row["code"], row.get("manifest"))
        row["loaded"] = code in self._loaded
        row["runtime_routes"] = routes
        row["client_routes"] = client_manifest["routes"]
        row["capabilities"] = client_manifest["capabilities"]
        return row

    async def list_modules(
        self,
        *,
        name: str | None = None,
        status: int | None = None,
        source_type: str | None = None,
    ) -> list[dict[str, Any]]:
        queryset = SystemRuntimeModule.filter(is_del=False)
        if name:
            queryset = queryset.filter(name__icontains=name)
        if status is not None:
            queryset = queryset.filter(status=status)
        if source_type:
            queryset = queryset.filter(source_type=source_type)

        rows = await queryset.order_by("-created_at").values()
        result = []
        for row in rows:
            client_manifest = self._resolve_client_manifest(row["code"], row.get("manifest"))
            row["loaded"] = row["code"] in self._loaded
            row["client_routes"] = client_manifest["routes"]
            row["capabilities"] = client_manifest["capabilities"]
            result.append(row)
        return result

    async def get_client_bootstrap(self) -> dict[str, Any]:
        modules: list[dict[str, Any]] = []
        for code, loaded in sorted(self._loaded.items()):
            record = await self._get_record_by_code(code)
            if not record:
                continue

            client_manifest = self._resolve_client_manifest(code, loaded.manifest)
            if not client_manifest["routes"] and not client_manifest["capabilities"]:
                continue

            modules.append(
                {
                    "code": code,
                    "name": record["name"],
                    "version": record.get("version") or "1.0.0",
                    "updated_at": record.get("updated_at"),
                    "routes": client_manifest["routes"],
                    "capabilities": client_manifest["capabilities"],
                }
            )

        return {
            "revision": self.revision,
            "modules": modules,
        }

    async def resolve_client_asset(self, module_code: str, entry: str) -> Path:
        record = await self._get_record_by_code(module_code)
        if not record:
            raise RuntimeModuleError("Module does not exist")

        normalized_entry = self._normalize_asset_entry(entry)
        install_path = Path(record["install_path"]).resolve()
        target_path = (install_path / normalized_entry).resolve()

        if install_path not in target_path.parents and target_path != install_path:
            raise RuntimeModuleError("Client asset path is invalid")
        if not target_path.exists() or not target_path.is_file():
            raise RuntimeModuleError("Client asset does not exist")
        return target_path

    async def dispatch(self, module_code: str, route_path: str, request: Request) -> Any:
        loaded = self._loaded.get(module_code)
        if not loaded:
            raise RuntimeModuleError("Module is not loaded")

        normalized_path = self._normalize_module_path(route_path)
        route = loaded.routes.get((request.method.upper(), normalized_path))
        if not route:
            raise RuntimeModuleError(f"Route not found: {request.method.upper()} {normalized_path}")

        handler = getattr(loaded.instance, route.handler)
        result = handler(request)
        if inspect.isawaitable(result):
            result = await result
        return result

    def list_examples(self) -> list[dict[str, Any]]:
        self._ensure_directories()
        examples: list[dict[str, Any]] = []
        for manifest_path in sorted(RUNTIME_MODULE_EXAMPLES.glob("*/manifest.json")):
            try:
                manifest = self._validate_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
                examples.append(
                    {
                        "code": manifest["code"],
                        "name": manifest["name"],
                        "version": manifest["version"],
                        "description": manifest["description"],
                        "author": manifest["author"],
                    }
                )
            except Exception:  # noqa: BLE001
                continue
        return examples


runtime_module_manager = RuntimeModuleManager()
