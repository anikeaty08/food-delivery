import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class AgentDefinition(BaseModel):
    id: str
    role: str
    goal: str
    model: str
    reasoning_effort: str = "low"
    allowed_tools: list[str] = Field(default_factory=list)
    handoff_targets: list[str] = Field(default_factory=list)
    safety_level: str = "standard"

    @field_validator("id")
    @classmethod
    def id_must_be_slug(cls, value: str) -> str:
        if not value.replace("_", "").isalnum():
            raise ValueError("agent id must contain only letters, numbers, and underscores")
        return value


class AgentRegistry:
    def __init__(self, agents: list[AgentDefinition]):
        self._agents = {agent.id: agent for agent in agents}
        self._validate_handoffs()

    @classmethod
    def from_yaml(cls, path: Path, env: dict[str, str] | None = None) -> "AgentRegistry":
        env_values = env or os.environ
        raw = path.read_text(encoding="utf-8")
        expanded = _expand_env(raw, env_values)
        parsed = yaml.safe_load(expanded) or {}
        agents = [AgentDefinition.model_validate(item) for item in parsed.get("agents", [])]
        if not agents:
            raise ValueError(f"No agents found in {path}")
        return cls(agents)

    def all(self) -> list[AgentDefinition]:
        return list(self._agents.values())

    def get(self, agent_id: str) -> AgentDefinition:
        try:
            return self._agents[agent_id]
        except KeyError as exc:
            raise KeyError(f"Unknown agent '{agent_id}'") from exc

    def can_handoff(self, source_agent_id: str, target_agent_id: str) -> bool:
        return target_agent_id in self.get(source_agent_id).handoff_targets

    def assert_tool_group_allowed(self, agent_id: str, tool_group: str) -> None:
        agent = self.get(agent_id)
        if tool_group not in agent.allowed_tools:
            raise PermissionError(f"{agent_id} cannot use {tool_group} tools")

    def _validate_handoffs(self) -> None:
        missing: list[str] = []
        for agent in self._agents.values():
            for target in agent.handoff_targets:
                if target not in self._agents:
                    missing.append(f"{agent.id}->{target}")
        if missing:
            raise ValueError(f"Invalid handoff targets: {', '.join(missing)}")


def _expand_env(text: str, env: dict[str, str]) -> str:
    out = text
    for key, value in env.items():
        out = out.replace("${" + key + "}", value)
    return out


class CrewAgentFactory:
    """Creates CrewAI Agent objects from config when CrewAI is installed."""

    def build(self, definition: AgentDefinition) -> Any:
        try:
            from crewai import Agent
        except ImportError as exc:
            raise RuntimeError("CrewAI is not installed. Run `pip install -e .` first.") from exc
        return Agent(
            role=definition.role,
            goal=definition.goal,
            backstory=(
                "You are one member of a Swiggy ordering bot crew. "
                "Use only your configured tools and hand off when another agent owns the task."
            ),
            llm=definition.model,
            verbose=False,
        )
