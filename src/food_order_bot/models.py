from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlmodel import Field, SQLModel


class Provider(StrEnum):
    SWIGGY = "swiggy"


class SwiggySurface(StrEnum):
    FOOD = "food"
    INSTAMART = "instamart"
    DINEOUT = "dineout"


class ConfirmationStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


def utc_now() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    telegram_user_id: int = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProviderAuth(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    provider: Provider = Field(index=True)
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scopes: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ChatSession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    telegram_chat_id: int = Field(index=True)
    last_surface: SwiggySurface | None = None
    last_intent: str | None = None
    state_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PendingConfirmation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    chat_id: int = Field(index=True)
    provider: Provider = Field(default=Provider.SWIGGY)
    surface: SwiggySurface
    tool_name: str
    summary: str
    arguments_json: str
    expected_phrase: str = "CONFIRM ORDER"
    status: ConfirmationStatus = Field(default=ConfirmationStatus.PENDING, index=True)
    expires_at: datetime = Field(default_factory=lambda: utc_now() + timedelta(minutes=10))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class OrderSnapshot(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    provider: Provider = Field(default=Provider.SWIGGY)
    surface: SwiggySurface = Field(index=True)
    external_order_id: str | None = Field(default=None, index=True)
    snapshot_json: str
    created_at: datetime = Field(default_factory=utc_now)


class AuditLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, index=True)
    event_type: str = Field(index=True)
    payload_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now)


class AgentRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, index=True)
    agent_id: str = Field(index=True)
    input_json: str
    output_json: str = "{}"
    status: str = Field(default="started", index=True)
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
