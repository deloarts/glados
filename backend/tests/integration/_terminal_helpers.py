"""Shared pieces of the terminal and infoscreen integration tests: a device
with its own Ed25519 key pair that signs in like a glados-terminal bridge,
the security settings row the terminal endpoints read, and clients that
call from a chosen address."""

import base64
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.hazmat.primitives.serialization import PublicFormat
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings

DEVICE = "/api/v1/web/terminal-device"
TERMINALS = "/api/v1/web/terminals"
INFOSCREENS = "/api/v1/web/infoscreens"
TERMINAL_KEYS = "/api/v1/web/admin/api-keys/terminal"


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class Device:
    """A display: its key pair and how its page signs in."""

    def __init__(self) -> None:
        self._private = Ed25519PrivateKey.generate()
        self.public_key = b64url(
            self._private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        )

    def sign(self, nonce: str) -> str:
        return b64url(self._private.sign(b"glados-terminal-auth-v1:" + nonce.encode("ascii")))

    async def challenge(self, client: httpx.AsyncClient) -> str:
        response = await client.post(f"{DEVICE}/challenge", json={"public_key": self.public_key})
        assert response.status_code == 200, response.text
        nonce: str = response.json()["nonce"]
        return nonce

    def session_body(self, nonce: str, **overrides: Any) -> dict[str, Any]:
        body: dict[str, Any] = {
            "public_key": self.public_key,
            "nonce": nonce,
            "signature": self.sign(nonce),
            "user_agent": "Chromium kiosk",
            "screen_width": 1920,
            "screen_height": 1080,
            "frontend_version": "1.2.3",
            "bridge_version": "0.2.0",
        }
        body.update(overrides)
        return body

    async def start_session(
        self, client: httpx.AsyncClient, api_key: str | None = None
    ) -> httpx.Response:
        nonce = await self.challenge(client)
        headers = {"X-Api-Key": api_key} if api_key else {}
        return await client.post(
            f"{DEVICE}/session", json=self.session_body(nonce), headers=headers
        )

    async def token(self, client: httpx.AsyncClient, api_key: str | None = None) -> str:
        response = await self.start_session(client, api_key)
        assert response.status_code == 200, response.text
        token: str = response.json()["access_token"]
        return token


def device_client(ip: str = "10.0.0.5") -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=(ip, 50000)),
        base_url="http://testserver",
    )


async def seed_security(db: AsyncSession, **overrides: Any) -> None:
    fields: dict[str, Any] = {
        "id": 1,
        "enforce_totp": False,
        "allow_rfid_login": True,
        "allow_local_login": True,
        "enable_api_key_auth": True,
        "min_password_length": 8,
        "session_timeout_minutes": 1440,
        "totp_trusted_device_days": 30,
        "max_login_attempts": 0,
        "lockout_duration_minutes": 15,
        "token_max_lifetime_days": 3650,
        "enable_terminals": True,
        "terminal_allowed_ips": [],
    }
    fields.update(overrides)
    await SqlAlchemyAdminSettingsRepository(db).save_security(AdminSecuritySettings(**fields))
    await db.commit()


async def seed_production(db: AsyncSession) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_production(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PON-{yy}-{seq:05d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=0,
            response_time_days=1,
            require_qa=False,
        )
    )
    await db.commit()
