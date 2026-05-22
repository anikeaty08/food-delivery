import json
from typing import Any

from sqlmodel import Session
from telegram import Update
from telegram.ext import ContextTypes

from food_order_bot.auth.oauth import SwiggyOAuth
from food_order_bot.mcp.client import McpError
from food_order_bot.models import Provider, SwiggySurface
from food_order_bot.repositories import (
    AuditRepository,
    AuthRepository,
    ConfirmationRepository,
    SessionRepository,
    UserRepository,
)
from food_order_bot.safety.confirmation import CONFIRMATION_PHRASE, ConfirmationGate
from food_order_bot.services.swiggy import SwiggyService
from food_order_bot.settings import Settings

HELP_TEXT = f"""
Swiggy Agent Bot

/connect - connect your Swiggy account
/search <food|instamart|dineout> <query> - search Swiggy
/menu <food|dineout> <restaurant_id> - fetch menu/details
/cart <food|instamart|dineout> - show cart or booking cart
/checkout <food|instamart|dineout> {{json_args}} - prepare checkout
/track <food|instamart|dineout> <order_or_booking_id> - track status
/cancel - cancel pending checkout

Checkout only runs after you reply exactly: {CONFIRMATION_PHRASE}
""".strip()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(
        update,
        "Welcome. I can help you order from Swiggy with safety checks.\n\n" + HELP_TEXT,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(update, HELP_TEXT)


async def connect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    oauth: SwiggyOAuth = context.bot_data["oauth"]
    if update.effective_user is None:
        await _reply(update, "I could not identify your Telegram user.")
        return
    try:
        start_state = oauth.start_url(update.effective_user.id)
    except RuntimeError as exc:
        await _reply(update, f"OAuth is not configured yet: {exc}")
        return
    context.bot_data["oauth_states"][start_state.state] = {
        "telegram_user_id": update.effective_user.id,
        "verifier": start_state.verifier,
    }
    await _reply(
        update,
        "Open this link to connect Swiggy:\n"
        f"{start_state.url}\n\n"
        "Callback URL must be whitelisted by Swiggy: "
        f"{settings.public_base_url}/auth/swiggy/callback",
    )


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    surface, rest = _parse_surface_and_rest(context.args)
    if not rest:
        await _reply(update, "Usage: /search <food|instamart|dineout> <query>")
        return
    await _with_service(update, context, "search", surface, {"query": " ".join(rest)})


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    surface, rest = _parse_surface_and_rest(context.args)
    if surface == SwiggySurface.INSTAMART:
        await _reply(
            update,
            "Instamart menu/details is not a restaurant-menu flow. "
            "Use /search instamart <query>.",
        )
        return
    if not rest:
        await _reply(update, "Usage: /menu <food|dineout> <restaurant_id>")
        return
    await _with_service(update, context, "menu", surface, {"item_id": rest[0]})


async def cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    surface, _rest = _parse_surface_and_rest(context.args)
    await _with_service(update, context, "cart", surface, {})


async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    surface, rest = _parse_surface_and_rest(context.args)
    args_text = " ".join(rest).strip()
    try:
        arguments = json.loads(args_text) if args_text else {}
    except json.JSONDecodeError as exc:
        await _reply(update, f"Checkout arguments must be JSON: {exc}")
        return
    await _with_service(update, context, "checkout", surface, {"arguments": arguments})


async def track(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    surface, rest = _parse_surface_and_rest(context.args)
    if not rest:
        await _reply(update, "Usage: /track <food|instamart|dineout> <order_or_booking_id>")
        return
    await _with_service(update, context, "track", surface, {"order_id": rest[0]})


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user, chat_id, session = _context_ids(update)
    if user is None or chat_id is None:
        await _reply(update, "I could not identify this chat.")
        return
    with Session(context.bot_data["engine"]) as db:
        app_user = UserRepository(db).get_or_create_telegram_user(user)
        ConfirmationRepository(db).cancel_open(app_user.id, chat_id)
    await _reply(update, "Cancelled any pending checkout.")


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _confirm_text(update, context, CONFIRMATION_PHRASE)


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text if update.message else ""
    if text.strip().upper() == CONFIRMATION_PHRASE:
        await _confirm_text(update, context, text)
        return
    await _reply(update, "I’m command-based for v1. Use /help to see what I can do.")


async def _confirm_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    user, chat_id, _session = _context_ids(update)
    if user is None or chat_id is None:
        await _reply(update, "I could not identify this chat.")
        return
    with Session(context.bot_data["engine"]) as db:
        app_user = UserRepository(db).get_or_create_telegram_user(user)
        auth = AuthRepository(db).get_auth(app_user.id, Provider.SWIGGY)
        gate = ConfirmationGate(ConfirmationRepository(db))
        result = gate.confirm(app_user.id, chat_id, text)
        if not result.ok or result.pending is None:
            await _reply(update, result.message)
            return
        service = _service(context, gate)
        try:
            checkout_result = await service.run_confirmed_checkout(
                access_token=auth.access_token if auth else None,
                pending=result.pending,
            )
        except McpError as exc:
            await _reply(update, f"Checkout failed: {exc}")
            return
        AuditRepository(db).write(
            "checkout_confirmed",
            {"pending_id": result.pending.id, "tool": result.pending.tool_name},
            app_user.id,
        )
    await _reply(update, checkout_result.message)


async def _with_service(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action: str,
    surface: SwiggySurface,
    payload: dict[str, Any],
) -> None:
    user, chat_id, _session = _context_ids(update)
    if user is None or chat_id is None:
        await _reply(update, "I could not identify this chat.")
        return
    with Session(context.bot_data["engine"]) as db:
        app_user = UserRepository(db).get_or_create_telegram_user(user)
        SessionRepository(db).get_or_create(app_user.id, chat_id)
        auth = AuthRepository(db).get_auth(app_user.id, Provider.SWIGGY)
        gate = ConfirmationGate(ConfirmationRepository(db))
        service = _service(context, gate)
        try:
            if action == "search":
                result = await service.search(
                    access_token=auth.access_token if auth else None,
                    query=payload["query"],
                    surface=surface,
                )
            elif action == "menu":
                result = await service.menu_or_details(
                    access_token=auth.access_token if auth else None,
                    surface=surface,
                    item_id=payload["item_id"],
                )
            elif action == "cart":
                result = await service.cart(
                    access_token=auth.access_token if auth else None,
                    surface=surface,
                )
            elif action == "checkout":
                result = await service.create_checkout_confirmation(
                    user_id=app_user.id,
                    chat_id=chat_id,
                    surface=surface,
                    arguments=payload["arguments"],
                )
            elif action == "track":
                result = await service.track(
                    access_token=auth.access_token if auth else None,
                    surface=surface,
                    order_id=payload["order_id"],
                )
            else:
                await _reply(update, "Unknown action.")
                return
        except McpError as exc:
            await _reply(update, f"{exc.code}: {exc}")
            return
        AuditRepository(db).write(
            f"telegram_{action}",
            {"surface": surface.value, "payload": payload},
            app_user.id,
        )
    await _reply(update, result.message)


def _service(context: ContextTypes.DEFAULT_TYPE, gate: ConfirmationGate) -> SwiggyService:
    return SwiggyService(
        settings=context.bot_data["settings"],
        orchestrator=context.bot_data["orchestrator"],
        confirmation_gate=gate,
    )


def _parse_surface_and_rest(args: list[str]) -> tuple[SwiggySurface, list[str]]:
    if not args:
        return SwiggySurface.FOOD, []
    first = args[0].lower()
    aliases = {
        "food": SwiggySurface.FOOD,
        "swiggy": SwiggySurface.FOOD,
        "instamart": SwiggySurface.INSTAMART,
        "im": SwiggySurface.INSTAMART,
        "dineout": SwiggySurface.DINEOUT,
        "table": SwiggySurface.DINEOUT,
    }
    if first in aliases:
        return aliases[first], args[1:]
    return SwiggySurface.FOOD, args


def _context_ids(update: Update) -> tuple[int | None, int | None, Any]:
    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None
    return user_id, chat_id, None


async def _reply(update: Update, text: str) -> None:
    if update.message:
        await update.message.reply_text(text)
