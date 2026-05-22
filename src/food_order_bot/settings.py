from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    port: int = Field(default=3000, alias="PORT")
    public_base_url: str = Field(default="http://localhost:3000", alias="PUBLIC_BASE_URL")

    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    fast_model: str = Field(default="gpt-5.4-mini", alias="FAST_MODEL")
    deep_model: str = Field(default="gpt-5.5", alias="DEEP_MODEL")

    swiggy_client_id: str | None = Field(default=None, alias="SWIGGY_CLIENT_ID")
    swiggy_client_secret: str | None = Field(default=None, alias="SWIGGY_CLIENT_SECRET")
    dev_swiggy_access_token: str | None = Field(default=None, alias="DEV_SWIGGY_ACCESS_TOKEN")

    database_url: str = Field(default="sqlite:///./data/bot.db", alias="DATABASE_URL")
    agent_config_path: Path = Field(default=Path("config/agents.yaml"), alias="AGENT_CONFIG_PATH")
    session_secret: str = Field(default="change-me-in-dev", alias="SESSION_SECRET")


@lru_cache
def get_settings() -> Settings:
    return Settings()
