import json
from dataclasses import dataclass
from typing import Any

from food_order_bot.agents.orchestrator import AgentOrchestrator
from food_order_bot.mcp.client import McpClient, McpError
from food_order_bot.models import SwiggySurface
from food_order_bot.safety.confirmation import ConfirmationGate
from food_order_bot.settings import Settings


@dataclass(frozen=True)
class ServiceResult:
    message: str
    raw: dict[str, Any] | None = None


class SwiggyService:
    def __init__(
        self,
        *,
        settings: Settings,
        orchestrator: AgentOrchestrator,
        confirmation_gate: ConfirmationGate,
    ):
        self.settings = settings
        self.orchestrator = orchestrator
        self.confirmation_gate = confirmation_gate

    def token_for(self, stored_access_token: str | None) -> str:
        token = stored_access_token or self.settings.dev_swiggy_access_token
        if not token:
            raise McpError("Connect your Swiggy account first with /connect", code="AUTH_REQUIRED")
        return token

    async def search(
        self,
        *,
        access_token: str | None,
        query: str,
        surface: SwiggySurface,
        address_id: str | None = None,
        city: str | None = None,
    ) -> ServiceResult:
        tool, args = _search_tool(surface, query, address_id, city)
        self.orchestrator.assert_agent_can_call("search_agent", tool)
        result = await self._call(access_token, surface, tool, args)
        return ServiceResult(_brief_result(f"{surface.value} search", result), result)

    async def menu_or_details(
        self,
        *,
        access_token: str | None,
        surface: SwiggySurface,
        item_id: str,
    ) -> ServiceResult:
        tool = "get_restaurant_menu" if surface == SwiggySurface.FOOD else "get_restaurant_details"
        args = {"restaurant_id": item_id}
        self.orchestrator.assert_agent_can_call("search_agent", tool)
        result = await self._call(access_token, surface, tool, args)
        return ServiceResult(_brief_result("details", result), result)

    async def cart(self, *, access_token: str | None, surface: SwiggySurface) -> ServiceResult:
        tool = {
            SwiggySurface.FOOD: "get_food_cart",
            SwiggySurface.INSTAMART: "get_cart",
            SwiggySurface.DINEOUT: "create_cart",
        }[surface]
        self.orchestrator.assert_agent_can_call("cart_agent", tool)
        result = await self._call(access_token, surface, tool, {})
        return ServiceResult(_brief_result("cart", result), result)

    async def create_checkout_confirmation(
        self,
        *,
        user_id: int,
        chat_id: int,
        surface: SwiggySurface,
        arguments: dict[str, Any],
    ) -> ServiceResult:
        tool = {
            SwiggySurface.FOOD: "place_food_order",
            SwiggySurface.INSTAMART: "checkout",
            SwiggySurface.DINEOUT: "book_table",
        }[surface]
        self.orchestrator.assert_agent_can_call("checkout_safety_agent", tool)
        summary = (
            f"Ready to run Swiggy {surface.value} checkout tool `{tool}`.\n"
            f"Arguments: {json.dumps(arguments, ensure_ascii=False)}\n\n"
            "Reply exactly `CONFIRM ORDER` within 10 minutes to proceed."
        )
        pending = self.confirmation_gate.create_pending(
            user_id=user_id,
            chat_id=chat_id,
            surface=surface,
            tool_name=tool,
            summary=summary,
            arguments=arguments,
        )
        return ServiceResult(pending.summary)

    async def run_confirmed_checkout(
        self,
        *,
        access_token: str | None,
        pending,
    ) -> ServiceResult:
        self.orchestrator.assert_agent_can_call("checkout_safety_agent", pending.tool_name)
        args = self.confirmation_gate.pending_arguments(pending)
        result = await self._call(access_token, pending.surface, pending.tool_name, args)
        return ServiceResult(_brief_result("checkout", result), result)

    async def track(
        self,
        *,
        access_token: str | None,
        surface: SwiggySurface,
        order_id: str,
    ) -> ServiceResult:
        tool = {
            SwiggySurface.FOOD: "track_food_order",
            SwiggySurface.INSTAMART: "track_order",
            SwiggySurface.DINEOUT: "get_booking_status",
        }[surface]
        key = "booking_id" if surface == SwiggySurface.DINEOUT else "order_id"
        self.orchestrator.assert_agent_can_call("tracking_agent", tool)
        result = await self._call(access_token, surface, tool, {key: order_id})
        return ServiceResult(_brief_result("tracking", result), result)

    async def _call(
        self,
        access_token: str | None,
        surface: SwiggySurface,
        tool: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        client = McpClient(surface=surface, access_token=self.token_for(access_token))
        return await client.call_tool(tool, args)


def _search_tool(
    surface: SwiggySurface,
    query: str,
    address_id: str | None,
    city: str | None,
) -> tuple[str, dict[str, Any]]:
    if surface == SwiggySurface.FOOD:
        return "search_restaurants", _strip({"query": query, "addressId": address_id, "city": city})
    if surface == SwiggySurface.INSTAMART:
        return "search_products", _strip({"query": query, "addressId": address_id})
    return "search_restaurants_dineout", _strip({"query": query, "city": city})


def _strip(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value not in (None, "")}


def _brief_result(label: str, result: dict[str, Any]) -> str:
    if not result:
        return f"No {label} result returned."
    content = result.get("structuredContent") or result.get("content") or result
    preview = json.dumps(content, ensure_ascii=False, default=str)
    if len(preview) > 1600:
        preview = preview[:1600] + "..."
    return f"{label.title()} result:\n```json\n{preview}\n```"
