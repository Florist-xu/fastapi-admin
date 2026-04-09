from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Request


@dataclass(slots=True)
class RuntimeModuleContext:
    record_id: str
    code: str
    name: str
    version: str
    base_dir: Path
    manifest: dict[str, Any]
    config: dict[str, Any]


@dataclass(slots=True)
class RuntimeModuleRoute:
    path: str
    methods: list[str]
    handler: str
    summary: str = ""


class RuntimeModuleBase:
    def __init__(self, context: RuntimeModuleContext):
        self.context = context

    def get_routes(self) -> list[RuntimeModuleRoute | dict[str, Any]]:
        return []

    async def on_load(self) -> None:
        return None

    async def on_unload(self) -> None:
        return None


class RuntimeModuleError(Exception):
    pass


RuntimeModuleHandler = Any
RuntimeModuleRequest = Request
