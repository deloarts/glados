"""
RFID identifies, it does not authenticate.

An unauthenticated RFID login that returned a full unscoped session token
would make a cloned or guessed chip value a complete account takeover, so
no route mints a session from an RFID. RFID resolves to an operator
*identity* behind an existing session.

The first class asserts that `POST /api/v1/auth/login/rfid/{rfid}` does
not exist and that no route mints a session from an RFID. The rest cover
the identify route.
"""

import pytest
from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.infrastructure.security.rfid import rfid_lookup

RFID = "12345678"
IDENTIFY = "/api/v1/web/production-operators/identify"


@pytest.fixture
async def operator(create_user, db):
    """A normal person whose chip is registered."""
    user = await create_user(username="operator", email="op@example.com")
    user.rfid_lookup = rfid_lookup(RFID)
    saved = await SqlAlchemyUserRepository(db).save(user)
    await db.commit()
    return saved


async def _set_rfid_enabled(db, enabled: bool) -> None:
    await db.execute(text("DELETE FROM admin_security_settings"))
    await db.commit()
    await SqlAlchemyAdminSettingsRepository(db).save_security(
        AdminSecuritySettings(
            id=1,
            enforce_totp=False,
            allow_rfid_login=enabled,
            allow_local_login=True,
            enable_api_key_auth=False,
            min_password_length=8,
            session_timeout_minutes=0,
            totp_trusted_device_days=0,
            max_login_attempts=0,
            lockout_duration_minutes=15,
            token_max_lifetime_days=3650,
        )
    )
    await db.commit()


@pytest.fixture
async def rfid_enabled(db):
    await _set_rfid_enabled(db, True)


# ── No RFID login endpoint ────────────────────────────────────────────


class TestRfidLoginEndpointIsGone:
    async def test_the_old_login_route_no_longer_exists(self, client, operator):
        """An unauthenticated RFID login route is a 404."""
        response = await client.post(f"/api/v1/auth/login/rfid/{RFID}")

        assert response.status_code == 404

    def test_no_route_anywhere_mints_a_session_from_an_rfid(self):
        from src.bootstrap.main import app

        rfid_routes = [
            r.path
            for r in app.routes
            if hasattr(r, "path") and "rfid" in r.path.lower() and "/auth/" in r.path
        ]
        assert rfid_routes == []


# ── Identification requires a real session ────────────────────────────


class TestIdentifyRequiresASession:
    async def test_unauthenticated_is_rejected(self, client, operator, rfid_enabled):
        assert (await client.post(IDENTIFY, json={"rfid": RFID})).status_code == 401

    async def test_a_garbage_token_is_rejected(self, client, operator, rfid_enabled):
        client.headers.update({"Authorization": "Bearer not-a-jwt"})

        assert (await client.post(IDENTIFY, json={"rfid": RFID})).status_code == 401


# ── Identification returns an identity, never a token ─────────────────


class TestIdentify:
    async def test_returns_the_operator(self, auth_client, operator, rfid_enabled):
        response = await (await auth_client()).post(IDENTIFY, json={"rfid": RFID})

        assert response.status_code == 200
        assert response.json()["id"] == operator.id
        assert response.json()["username"] == "operator"

    async def test_response_contains_no_token(self, auth_client, operator, rfid_enabled):
        """The whole point: this hands back who you are, not a session."""
        body = (await (await auth_client()).post(IDENTIFY, json={"rfid": RFID})).json()

        assert "access_token" not in body
        assert "token_type" not in body

    async def test_unknown_rfid_is_404(self, auth_client, operator, rfid_enabled):
        assert (
            await (await auth_client()).post(IDENTIFY, json={"rfid": "87654321"})
        ).status_code == 404

    async def test_short_rfid_is_rejected_by_validation(self, auth_client, operator, rfid_enabled):
        assert (await (await auth_client()).post(IDENTIFY, json={"rfid": "123"})).status_code == 422

    async def test_inactive_operator_is_not_identified(
        self, auth_client, create_user, db, rfid_enabled
    ):
        user = await create_user(username="gone", email="gone@example.com", is_active=False)
        user.rfid_lookup = rfid_lookup("99999999")
        await SqlAlchemyUserRepository(db).save(user)
        await db.commit()

        assert (
            await (await auth_client()).post(IDENTIFY, json={"rfid": "99999999"})
        ).status_code == 404

    async def test_disabled_in_settings_is_403(self, auth_client, operator, db):
        await _set_rfid_enabled(db, False)

        assert (await (await auth_client()).post(IDENTIFY, json={"rfid": RFID})).status_code == 403

    async def test_the_admin_toggle_actually_takes_effect(self, auth_client, operator, db):
        """The check reads the admin setting, not the env value, so flipping
        it in the admin UI takes effect."""
        client = await auth_client()

        await _set_rfid_enabled(db, True)
        assert (await client.post(IDENTIFY, json={"rfid": RFID})).status_code == 200

        await _set_rfid_enabled(db, False)
        assert (await client.post(IDENTIFY, json={"rfid": RFID})).status_code == 403
