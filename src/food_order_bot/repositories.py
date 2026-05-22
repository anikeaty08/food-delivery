import json
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from food_order_bot.models import (
    AuditLog,
    ChatSession,
    ConfirmationStatus,
    PendingConfirmation,
    Provider,
    ProviderAuth,
    SwiggySurface,
    User,
    utc_now,
)


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_or_create_telegram_user(self, telegram_user_id: int) -> User:
        user = self.session.exec(
            select(User).where(User.telegram_user_id == telegram_user_id)
        ).first()
        if user:
            return user
        user = User(telegram_user_id=telegram_user_id)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user


class AuthRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_auth(self, user_id: int, provider: Provider = Provider.SWIGGY) -> ProviderAuth | None:
        return self.session.exec(
            select(ProviderAuth).where(
                ProviderAuth.user_id == user_id,
                ProviderAuth.provider == provider,
            )
        ).first()

    def save_auth(
        self,
        user_id: int,
        access_token: str,
        refresh_token: str | None = None,
        expires_at: datetime | None = None,
        scopes: str | None = None,
        provider: Provider = Provider.SWIGGY,
    ) -> ProviderAuth:
        auth = self.get_auth(user_id, provider)
        if auth is None:
            auth = ProviderAuth(
                user_id=user_id,
                provider=provider,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                scopes=scopes,
            )
            self.session.add(auth)
        else:
            auth.access_token = access_token
            auth.refresh_token = refresh_token
            auth.expires_at = expires_at
            auth.scopes = scopes
            auth.updated_at = utc_now()
        self.session.commit()
        self.session.refresh(auth)
        return auth


class SessionRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_or_create(self, user_id: int, telegram_chat_id: int) -> ChatSession:
        chat = self.session.exec(
            select(ChatSession).where(
                ChatSession.user_id == user_id,
                ChatSession.telegram_chat_id == telegram_chat_id,
            )
        ).first()
        if chat:
            return chat
        chat = ChatSession(user_id=user_id, telegram_chat_id=telegram_chat_id)
        self.session.add(chat)
        self.session.commit()
        self.session.refresh(chat)
        return chat

    def update_state(
        self,
        chat: ChatSession,
        *,
        last_surface: SwiggySurface | None = None,
        last_intent: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> ChatSession:
        if last_surface is not None:
            chat.last_surface = last_surface
        if last_intent is not None:
            chat.last_intent = last_intent
        if state is not None:
            chat.state_json = json.dumps(state)
        chat.updated_at = utc_now()
        self.session.add(chat)
        self.session.commit()
        self.session.refresh(chat)
        return chat


class ConfirmationRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        user_id: int,
        chat_id: int,
        surface: SwiggySurface,
        tool_name: str,
        summary: str,
        arguments: dict[str, Any],
    ) -> PendingConfirmation:
        self.cancel_open(user_id, chat_id)
        pending = PendingConfirmation(
            user_id=user_id,
            chat_id=chat_id,
            surface=surface,
            tool_name=tool_name,
            summary=summary,
            arguments_json=json.dumps(arguments),
        )
        self.session.add(pending)
        self.session.commit()
        self.session.refresh(pending)
        return pending

    def get_open(self, user_id: int, chat_id: int) -> PendingConfirmation | None:
        now = datetime.now(UTC)
        pending = self.session.exec(
            select(PendingConfirmation).where(
                PendingConfirmation.user_id == user_id,
                PendingConfirmation.chat_id == chat_id,
                PendingConfirmation.status == ConfirmationStatus.PENDING,
            )
        ).first()
        if pending and pending.expires_at <= now:
            pending.status = ConfirmationStatus.EXPIRED
            pending.updated_at = utc_now()
            self.session.add(pending)
            self.session.commit()
            return None
        return pending

    def mark_confirmed(self, pending: PendingConfirmation) -> PendingConfirmation:
        pending.status = ConfirmationStatus.CONFIRMED
        pending.updated_at = utc_now()
        self.session.add(pending)
        self.session.commit()
        self.session.refresh(pending)
        return pending

    def cancel_open(self, user_id: int, chat_id: int) -> None:
        open_items = self.session.exec(
            select(PendingConfirmation).where(
                PendingConfirmation.user_id == user_id,
                PendingConfirmation.chat_id == chat_id,
                PendingConfirmation.status == ConfirmationStatus.PENDING,
            )
        ).all()
        for item in open_items:
            item.status = ConfirmationStatus.CANCELLED
            item.updated_at = utc_now()
            self.session.add(item)
        self.session.commit()


class AuditRepository:
    def __init__(self, session: Session):
        self.session = session

    def write(self, event_type: str, payload: dict[str, Any], user_id: int | None = None) -> None:
        self.session.add(AuditLog(user_id=user_id, event_type=event_type, payload_json=json.dumps(payload)))
        self.session.commit()
