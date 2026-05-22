import json
from dataclasses import dataclass
from typing import Any

from food_order_bot.mcp.tools import ToolGroup, classify_tool
from food_order_bot.models import PendingConfirmation
from food_order_bot.repositories import ConfirmationRepository

CONFIRMATION_PHRASE = "CONFIRM ORDER"


@dataclass(frozen=True)
class ConfirmationResult:
    ok: bool
    message: str
    pending: PendingConfirmation | None = None


class ConfirmationGate:
    def __init__(self, repository: ConfirmationRepository):
        self.repository = repository

    def needs_confirmation(self, tool_name: str) -> bool:
        return classify_tool(tool_name) in {ToolGroup.CHECKOUT_PAYMENT, ToolGroup.BOOKING}

    def create_pending(
        self,
        *,
        user_id: int,
        chat_id: int,
        surface,
        tool_name: str,
        summary: str,
        arguments: dict[str, Any],
    ) -> PendingConfirmation:
        return self.repository.create(
            user_id=user_id,
            chat_id=chat_id,
            surface=surface,
            tool_name=tool_name,
            summary=summary,
            arguments=arguments,
        )

    def confirm(self, user_id: int, chat_id: int, text: str) -> ConfirmationResult:
        pending = self.repository.get_open(user_id, chat_id)
        if pending is None:
            return ConfirmationResult(False, "No active checkout is waiting for confirmation.")
        if text.strip().upper() != CONFIRMATION_PHRASE:
            return ConfirmationResult(
                False,
                f"To place this order, reply exactly: {CONFIRMATION_PHRASE}",
                pending,
            )
        self.repository.mark_confirmed(pending)
        return ConfirmationResult(True, "Confirmed.", pending)

    def pending_arguments(self, pending: PendingConfirmation) -> dict[str, Any]:
        parsed = json.loads(pending.arguments_json)
        return parsed if isinstance(parsed, dict) else {}
