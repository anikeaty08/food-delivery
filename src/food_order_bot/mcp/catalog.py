from dataclasses import dataclass, field

from food_order_bot.mcp.client import McpClient
from food_order_bot.mcp.tools import ToolGroup, classify_tool
from food_order_bot.models import SwiggySurface


@dataclass
class ToolCatalog:
    tools_by_surface: dict[SwiggySurface, dict[str, ToolGroup]] = field(default_factory=dict)

    async def refresh_surface(self, client: McpClient) -> None:
        tools = await client.list_tools()
        self.tools_by_surface[client.surface] = {
            str(tool["name"]): classify_tool(str(tool["name"]))
            for tool in tools
            if isinstance(tool, dict) and tool.get("name")
        }

    def group_for(self, surface: SwiggySurface, tool_name: str) -> ToolGroup:
        known = self.tools_by_surface.get(surface, {})
        return known.get(tool_name, classify_tool(tool_name))
