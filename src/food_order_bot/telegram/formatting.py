from typing import Any

from telegram.constants import ParseMode


def code_block(text: str) -> str:
    escaped = text.replace("`", "'")
    return f"```\n{escaped}\n```"


def markdown_response(text: str) -> dict[str, Any]:
    return {"text": text, "parse_mode": ParseMode.MARKDOWN}
