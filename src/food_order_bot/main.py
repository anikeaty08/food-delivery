import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlmodel import Session
from telegram import Update

from food_order_bot.agents.orchestrator import AgentOrchestrator
from food_order_bot.agents.registry import AgentRegistry
from food_order_bot.auth.oauth import SwiggyOAuth
from food_order_bot.db import create_db_engine, init_db
from food_order_bot.repositories import AuthRepository, UserRepository
from food_order_bot.settings import Settings, get_settings
from food_order_bot.telegram import build_telegram_app


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = create_db_engine(settings)
    registry = AgentRegistry.from_yaml(
        settings.agent_config_path,
        env={
            "FAST_MODEL": settings.fast_model,
            "DEEP_MODEL": settings.deep_model,
        },
    )
    orchestrator = AgentOrchestrator(registry)
    oauth = SwiggyOAuth(settings)
    telegram_app = build_telegram_app(settings)

    app = FastAPI(title="Swiggy Agent Bot", version="0.1.0")
    app.state.settings = settings
    app.state.engine = engine
    app.state.registry = registry
    app.state.orchestrator = orchestrator
    app.state.oauth = oauth
    app.state.telegram_app = telegram_app
    app.state.oauth_states = {}

    if telegram_app:
        telegram_app.bot_data["settings"] = settings
        telegram_app.bot_data["engine"] = engine
        telegram_app.bot_data["registry"] = registry
        telegram_app.bot_data["orchestrator"] = orchestrator
        telegram_app.bot_data["oauth"] = oauth
        telegram_app.bot_data["oauth_states"] = app.state.oauth_states

    @app.on_event("startup")
    async def startup() -> None:
        init_db(engine)
        if telegram_app:
            await telegram_app.initialize()
            await telegram_app.start()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        if telegram_app:
            await telegram_app.stop()
            await telegram_app.shutdown()

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "ok": True,
            "telegram_enabled": telegram_app is not None,
            "agents": [agent.id for agent in registry.all()],
        }

    @app.post("/telegram/webhook")
    async def telegram_webhook(request: Request) -> dict[str, bool]:
        if telegram_app is None:
            raise HTTPException(status_code=503, detail="Telegram is not configured")
        payload = await request.json()
        update = Update.de_json(payload, telegram_app.bot)
        await telegram_app.process_update(update)
        return {"ok": True}

    @app.get("/auth/swiggy/start")
    async def auth_start(telegram_user_id: int) -> dict[str, str]:
        start_state = oauth.start_url(telegram_user_id)
        app.state.oauth_states[start_state.state] = {
            "telegram_user_id": telegram_user_id,
            "verifier": start_state.verifier,
        }
        return {"url": start_state.url}

    @app.get("/auth/swiggy/callback", response_class=PlainTextResponse)
    async def auth_callback(code: str, state: str) -> str:
        try:
            telegram_user_id_raw, nonce = state.split(":", 1)
            telegram_user_id = int(telegram_user_id_raw)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid OAuth state") from exc
        stored = app.state.oauth_states.pop(nonce, None)
        if stored is None or stored["telegram_user_id"] != telegram_user_id:
            raise HTTPException(status_code=400, detail="OAuth state expired or invalid")
        token = await oauth.exchange_code(code, stored["verifier"])
        with Session(engine) as db:
            user = UserRepository(db).get_or_create_telegram_user(telegram_user_id)
            AuthRepository(db).save_auth(
                user_id=user.id,
                access_token=token.access_token,
                refresh_token=token.refresh_token,
                expires_at=token.expires_at,
                scopes=token.scopes,
            )
        return "Swiggy connected. You can return to Telegram."

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run("food_order_bot.main:app", host="0.0.0.0", port=settings.port, reload=False)


if __name__ == "__main__":
    run()
