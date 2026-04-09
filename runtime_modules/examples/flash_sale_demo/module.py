from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from runtime_modules.base import RuntimeModuleBase, RuntimeModuleRoute


class Module(RuntimeModuleBase):
    def __init__(self, context):
        super().__init__(context)
        self._orders: list[dict[str, Any]] = []
        self._setup_event()

    def get_routes(self) -> list[RuntimeModuleRoute]:
        return [
            RuntimeModuleRoute(path="/meta", methods=["GET"], handler="meta", summary="模块说明"),
            RuntimeModuleRoute(path="/state", methods=["GET"], handler="state", summary="活动状态"),
            RuntimeModuleRoute(path="/purchase", methods=["POST"], handler="purchase", summary="执行秒杀"),
            RuntimeModuleRoute(path="/reset", methods=["POST"], handler="reset", summary="重置活动"),
        ]

    def _setup_event(
        self,
        *,
        countdown_seconds: int | None = None,
        sale_duration_seconds: int | None = None,
        total_stock: int | None = None,
    ) -> None:
        config = self.context.config
        now = datetime.now()
        self._countdown_seconds = max(0, int(countdown_seconds or config.get("countdown_seconds", 90)))
        self._sale_duration_seconds = max(
            30,
            int(sale_duration_seconds or config.get("sale_duration_seconds", 180)),
        )
        self._total_stock = max(1, int(total_stock or config.get("total_stock", 20)))
        self._start_at = now + timedelta(seconds=self._countdown_seconds)
        self._end_at = self._start_at + timedelta(seconds=self._sale_duration_seconds)
        self._orders = []

    def _current_status(self) -> dict[str, Any]:
        now = datetime.now()
        sold_count = sum(order["quantity"] for order in self._orders)
        stock_left = max(0, self._total_stock - sold_count)

        if stock_left <= 0:
            status = "sold_out"
            remaining_seconds = 0
        elif now < self._start_at:
            status = "pending"
            remaining_seconds = max(0, int((self._start_at - now).total_seconds()))
        elif now <= self._end_at:
            status = "ongoing"
            remaining_seconds = max(0, int((self._end_at - now).total_seconds()))
        else:
            status = "ended"
            remaining_seconds = 0

        return {
            "module": self.context.code,
            "title": self.context.config.get("product_name", "秒杀活动"),
            "subtitle": self.context.config.get("product_subtitle", "限时抢购"),
            "original_price": float(self.context.config.get("original_price", 199)),
            "sale_price": float(self.context.config.get("sale_price", 29.9)),
            "total_stock": self._total_stock,
            "sold_count": sold_count,
            "stock_left": stock_left,
            "status": status,
            "countdown_seconds": remaining_seconds,
            "start_at": self._start_at.isoformat(),
            "end_at": self._end_at.isoformat(),
            "recent_orders": self._orders[-5:][::-1],
        }

    async def meta(self, request) -> dict[str, Any]:
        return {
            "title": self.context.config.get("product_name", "秒杀活动"),
            "version": self.context.version,
            "usage": {
                "state": f"/runtime-module/execute/{self.context.code}/state",
                "purchase": f"/runtime-module/execute/{self.context.code}/purchase",
                "reset": f"/runtime-module/execute/{self.context.code}/reset",
            },
            "config": self.context.config,
        }

    async def state(self, request) -> dict[str, Any]:
        return self._current_status()

    async def purchase(self, request) -> dict[str, Any]:
        payload = await request.json()
        buyer = str(payload.get("buyer") or "").strip()
        quantity = max(1, int(payload.get("quantity") or 1))

        if not buyer:
            return {"success": False, "message": "buyer 不能为空", "state": self._current_status()}

        state = self._current_status()
        if state["status"] == "pending":
            return {"success": False, "message": "活动未开始", "state": state}
        if state["status"] == "ended":
            return {"success": False, "message": "活动已结束", "state": state}
        if state["status"] == "sold_out":
            return {"success": False, "message": "商品已售罄", "state": state}
        if quantity > state["stock_left"]:
            return {"success": False, "message": "库存不足", "state": state}

        order = {
            "order_no": f"FS-{uuid4().hex[:8].upper()}",
            "buyer": buyer,
            "quantity": quantity,
            "paid_amount": round(quantity * float(state["sale_price"]), 2),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._orders.append(order)

        return {
          "success": True,
          "message": "抢购成功",
          "order": order,
          "state": self._current_status(),
        }

    async def reset(self, request) -> dict[str, Any]:
        payload = await request.json() if request.method.upper() == "POST" else {}
        self._setup_event(
            countdown_seconds=payload.get("countdown_seconds"),
            sale_duration_seconds=payload.get("sale_duration_seconds"),
            total_stock=payload.get("total_stock"),
        )
        return {
            "success": True,
            "message": "活动已重置",
            "state": self._current_status(),
        }
