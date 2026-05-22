from dataclasses import dataclass

from food_order_bot.agents.registry import AgentDefinition, AgentRegistry
from food_order_bot.mcp.tools import ToolGroup, classify_tool
from food_order_bot.models import SwiggySurface


@dataclass(frozen=True)
class RouteDecision:
    agent_id: str
    intent: str
    surface: SwiggySurface


class AgentOrchestrator:
    """Thin deterministic coordinator around config-driven agents.

    CrewAI owns agent definitions; this layer keeps critical commerce safety deterministic.
    """

    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    def route_command(self, command: str, text: str) -> RouteDecision:
        normalized = f"{command} {text}".lower()
        surface = _detect_surface(normalized)
        if command in {"search", "menu", "dineout"}:
            return RouteDecision("search_agent", command, surface)
        if command in {"cart"} or "add" in normalized:
            return RouteDecision("cart_agent", command, surface)
        if command in {"checkout"} or "book" in normalized or "payment" in normalized:
            return RouteDecision("checkout_safety_agent", command, surface)
        if command in {"track"}:
            return RouteDecision("tracking_agent", command, surface)
        return RouteDecision("router_agent", "unknown", surface)

    def assert_agent_can_call(self, agent: AgentDefinition | str, tool_name: str) -> ToolGroup:
        agent_id = agent if isinstance(agent, str) else agent.id
        group = classify_tool(tool_name)
        self.registry.assert_tool_group_allowed(agent_id, group.value)
        return group


def _detect_surface(text: str) -> SwiggySurface:
    if any(token in text for token in ("instamart", "grocery", "groceries", "milk", "bread")):
        return SwiggySurface.INSTAMART
    if any(token in text for token in ("dineout", "table", "booking", "reservation", "slot")):
        return SwiggySurface.DINEOUT
    return SwiggySurface.FOOD
