import asyncio
import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

from food_order_bot.mcp.tools import may_retry
from food_order_bot.models import SwiggySurface

PROTOCOL_VERSION = "2025-06-18"

SWIGGY_ENDPOINTS: dict[SwiggySurface, str] = {
    SwiggySurface.FOOD: "https://mcp.swiggy.com/food",
    SwiggySurface.INSTAMART: "https://mcp.swiggy.com/im",
    SwiggySurface.DINEOUT: "https://mcp.swiggy.com/dineout",
}


class McpError(RuntimeError):
    def __init__(self, message: str, *, code: str = "MCP_ERROR", details: Any = None):
        super().__init__(message)
        self.code = code
        self.details = details


@dataclass
class McpClient:
    surface: SwiggySurface
    access_token: str
    endpoint: str | None = None
    session_id: str | None = None
    initialized: bool = False

    @property
    def url(self) -> str:
        return self.endpoint or SWIGGY_ENDPOINTS[self.surface]

    async def initialize(self) -> None:
        if self.initialized:
            return
        await self._post(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "food-order-bot", "version": "0.1.0"},
            },
            retry=False,
        )
        await self._notify_initialized()
        self.initialized = True

    async def list_tools(self) -> list[dict[str, Any]]:
        await self.initialize()
        result = await self._post("tools/list", {}, retry=True)
        return list(result.get("tools", [])) if isinstance(result, dict) else []

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        await self.initialize()
        return await self._post(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
            retry=may_retry(tool_name),
        )

    async def _post(self, method: str, params: dict[str, Any], *, retry: bool) -> dict[str, Any]:
        attempts = 3 if retry else 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                return await self._single_post(method, params)
            except (httpx.TransportError, McpError) as exc:
                last_error = exc
                if not retry or attempt == attempts - 1:
                    break
                await asyncio.sleep(0.25 * (2**attempt))
        raise last_error or McpError("Unknown MCP failure")

    async def _single_post(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
            "mcp-protocol-version": PROTOCOL_VERSION,
            "authorization": f"Bearer {self.access_token}",
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        body = {"jsonrpc": "2.0", "id": str(uuid4()), "method": method, "params": params}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(self.url, headers=headers, json=body)
        if response.status_code in {401, 403}:
            raise McpError("Swiggy authentication required or expired", code="AUTH_REQUIRED")
        if response.status_code >= 400:
            raise McpError(f"Swiggy MCP HTTP {response.status_code}", details=response.text)
        session_id = response.headers.get("mcp-session-id")
        if session_id:
            self.session_id = session_id
        payload = await _parse_mcp_response(response)
        if "error" in payload:
            err = payload["error"]
            message = err.get("message", "Swiggy MCP returned an error") if isinstance(err, dict) else str(err)
            raise McpError(message, details=err)
        result = payload.get("result", {})
        return result if isinstance(result, dict) else {"result": result}

    async def _notify_initialized(self) -> None:
        headers = {
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
            "mcp-protocol-version": PROTOCOL_VERSION,
            "authorization": f"Bearer {self.access_token}",
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        body = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                await client.post(self.url, headers=headers, json=body)
            except httpx.TransportError:
                return


async def _parse_mcp_response(response: httpx.Response) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" not in content_type:
        return response.json()
    for event in response.text.split("\n\n"):
        data_lines = [line.removeprefix("data:").strip() for line in event.splitlines() if line.startswith("data:")]
        if not data_lines:
            continue
        try:
            parsed = json.loads("\n".join(data_lines))
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "id" in parsed:
            return parsed
    raise McpError("Empty MCP SSE response")
