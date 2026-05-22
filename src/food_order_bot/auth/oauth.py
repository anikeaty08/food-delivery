import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

from food_order_bot.settings import Settings

AUTHORIZATION_ENDPOINT = "https://mcp.swiggy.com/oauth/authorize"
TOKEN_ENDPOINT = "https://mcp.swiggy.com/oauth/token"


@dataclass(frozen=True)
class OAuthStart:
    url: str
    state: str
    verifier: str


@dataclass(frozen=True)
class OAuthToken:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scopes: str | None


class SwiggyOAuth:
    def __init__(self, settings: Settings):
        self.settings = settings

    def start_url(self, telegram_user_id: int) -> OAuthStart:
        if not self.settings.swiggy_client_id:
            raise RuntimeError("SWIGGY_CLIENT_ID is required for OAuth")
        verifier = secrets.token_urlsafe(48)
        challenge = _pkce_challenge(verifier)
        state = secrets.token_urlsafe(32)
        redirect_uri = self.redirect_uri
        params = {
            "response_type": "code",
            "client_id": self.settings.swiggy_client_id,
            "redirect_uri": redirect_uri,
            "state": f"{telegram_user_id}:{state}",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": "mcp",
        }
        return OAuthStart(f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}", state, verifier)

    @property
    def redirect_uri(self) -> str:
        return f"{self.settings.public_base_url.rstrip('/')}/auth/swiggy/callback"

    async def exchange_code(self, code: str, verifier: str) -> OAuthToken:
        if not self.settings.swiggy_client_id:
            raise RuntimeError("SWIGGY_CLIENT_ID is required for OAuth")
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.settings.swiggy_client_id,
            "code_verifier": verifier,
        }
        if self.settings.swiggy_client_secret:
            data["client_secret"] = self.settings.swiggy_client_secret
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                TOKEN_ENDPOINT,
                data=data,
                headers={"accept": "application/json"},
            )
        response.raise_for_status()
        payload = response.json()
        expires_in = payload.get("expires_in")
        expires_at = (
            datetime.now(UTC) + timedelta(seconds=int(expires_in))
            if expires_in
            else None
        )
        return OAuthToken(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=expires_at,
            scopes=payload.get("scope"),
        )


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
