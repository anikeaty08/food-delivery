import pytest

from food_order_bot.agents.orchestrator import AgentOrchestrator
from food_order_bot.agents.registry import AgentDefinition, AgentRegistry
from food_order_bot.models import SwiggySurface


def test_orchestrator_routes_instamart_search() -> None:
    registry = AgentRegistry(
        [
            AgentDefinition(
                id="search_agent",
                role="Search",
                goal="Search",
                model="fast",
                allowed_tools=["read_only"],
            )
        ]
    )
    decision = AgentOrchestrator(registry).route_command("search", "instamart milk")

    assert decision.agent_id == "search_agent"
    assert decision.surface == SwiggySurface.INSTAMART


def test_orchestrator_blocks_agent_tool_mismatch() -> None:
    registry = AgentRegistry(
        [
            AgentDefinition(
                id="search_agent",
                role="Search",
                goal="Search",
                model="fast",
                allowed_tools=["read_only"],
            )
        ]
    )

    with pytest.raises(PermissionError):
        AgentOrchestrator(registry).assert_agent_can_call("search_agent", "checkout")
