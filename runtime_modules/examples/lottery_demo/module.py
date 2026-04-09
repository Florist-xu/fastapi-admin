import random
from typing import Any

from runtime_modules.base import RuntimeModuleBase, RuntimeModuleRoute


class Module(RuntimeModuleBase):
    def get_routes(self) -> list[RuntimeModuleRoute]:
        return [
            RuntimeModuleRoute(path="/meta", methods=["GET"], handler="meta", summary="模块说明"),
            RuntimeModuleRoute(path="/draw", methods=["POST"], handler="draw", summary="执行抽奖"),
        ]

    async def meta(self, request) -> dict[str, Any]:
        return {
            "title": self.context.config.get("module_title", "抽奖活动"),
            "version": self.context.version,
            "default_winner_count": self.context.config.get("default_winner_count", 1),
            "usage": {
                "endpoint": f"/runtime-module/execute/{self.context.code}/draw",
                "method": "POST",
                "body": {
                    "participants": ["用户A", "用户B", "用户C"],
                    "winner_count": 1
                }
            }
        }

    async def draw(self, request) -> dict[str, Any]:
        payload = await request.json()
        participants = payload.get("participants") or []
        participants = [str(item).strip() for item in participants if str(item).strip()]
        if not participants:
            raise ValueError("participants 不能为空")

        winner_count = int(payload.get("winner_count") or self.context.config.get("default_winner_count") or 1)
        winner_count = max(1, min(winner_count, len(participants)))
        winners = random.sample(participants, winner_count)

        return {
            "module": self.context.code,
            "winner_count": winner_count,
            "participants": participants,
            "winners": winners,
        }
