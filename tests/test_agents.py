from pathlib import Path

import pytest

from food_order_bot.agents.registry import AgentRegistry


def test_agent_registry_loads_config() -> None:
    registry = AgentRegistry.from_yaml(
        Path("config/agents.yaml"),
        env={"FAST_MODEL": "fast", "DEEP_MODEL": "deep"},
    )

    assert registry.get("router_agent").model == "fast"
    assert registry.get("checkout_safety_agent").model == "deep"
    assert registry.can_handoff("router_agent", "search_agent")


def test_agent_registry_blocks_unapproved_tool_group() -> None:
    registry = AgentRegistry.from_yaml(
        Path("config/agents.yaml"),
        env={"FAST_MODEL": "fast", "DEEP_MODEL": "deep"},
    )

    with pytest.raises(PermissionError):
        registry.assert_tool_group_allowed("search_agent", "checkout_payment")
