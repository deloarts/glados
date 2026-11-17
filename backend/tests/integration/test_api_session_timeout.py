"""
`session_timeout_minutes` is an *idle* timeout on a server-side session
row, not a JWT expiry.

A login creates a row in user_session_table; the token's `sid` claim
names it and carries no `exp` at all. Liveness is decided per request
from the row: revoked_at set → dead, idle past the timeout → dead,
otherwise last_seen_at slides forward. `0` means "never idle-expires",
honoured literally, which is safe because the row is revocable, so a
session can always be ended without an expiry baked into the JWT.

Idle expiry is exercised by backdating last_seen_at directly in the DB,
there is no clock to freeze when the token itself never expires.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

import jwt
from sqlalchemy import text
from starlette.requests import Request

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_live_session_check
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.infrastructure.config.settings import cfg

PASSWORD = "test-password"


async def _set_timeout(db, minutes: int) -> None:
    await db.execute(text("DELETE FROM admin_security_settings"))
    await db.commit()
    await SqlAlchemyAdminSettingsRepository(db).save_security(
        AdminSecuritySettings(
            id=1,
            enforce_totp=False,
            allow_rfid_login=True,
            allow_local_login=True,
            enable_api_key_auth=False,
            min_password_length=8,
            session_timeout_minutes=minutes,
            totp_trusted_device_days=0,
            max_login_attempts=0,
            lockout_duration_minutes=15,
            token_max_lifetime_days=3650,
        )
    )
    await db.commit()


async def _login(client, username="tester"):
    return await client.post(
        "/api/v1/auth/login/access-token",
        data={"username": username, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def _decode(token: str) -> dict:
    return jwt.decode(
        token,
        cfg.security.secret_key_non_persistent,
        algorithms=[cfg.security.algorithm],
        options={"verify_exp": False},
    )


async def _backdate_last_seen(db, minutes: int) -> None:
    """Pretend every session has been idle for `minutes`."""
    await db.execute(
        text("UPDATE user_session_table SET last_seen_at = :when"),
        {"when": datetime.now(UTC) - timedelta(minutes=minutes)},
    )
    await db.commit()


async def _me(client, token: str, idle_seconds: int | None = None):
    headers = {"Authorization": f"Bearer {token}"}
    if idle_seconds is not None:
        headers["X-Glados-Idle-Seconds"] = str(idle_seconds)
    return await client.get("/api/v1/web/users/me", headers=headers)


async def _last_seen(db) -> datetime:
    value = (await db.execute(text("SELECT last_seen_at FROM user_session_table"))).scalar_one()
    stamp = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)


class TestSessionTokenShape:
    async def test_login_creates_a_session_row_the_token_points_at(self, client, create_user, db):
        await create_user()
        await _set_timeout(db, 30)

        token = (await _login(client)).json()["access_token"]
        sid = _decode(token)["sid"]

        row = (await db.execute(text("SELECT public_id FROM user_session_table"))).fetchone()
        assert row is not None
        assert str(sid).replace("-", "") == str(row[0]).replace("-", "")

    async def test_session_tokens_carry_no_exp_claim(self, client, create_user, db):
        """Expiry lives in the row (idle rule), not in the JWT."""
        await create_user()
        await _set_timeout(db, 30)

        raw = _decode((await _login(client)).json()["access_token"])

        assert "exp" not in raw


class TestIdleTimeout:
    async def test_a_fresh_session_is_usable(self, client, create_user, db):
        await create_user()
        await _set_timeout(db, 30)

        token = (await _login(client)).json()["access_token"]

        assert (await _me(client, token)).status_code == 200

    async def test_an_idle_session_expires(self, client, create_user, db):
        await create_user()
        await _set_timeout(db, 30)
        token = (await _login(client)).json()["access_token"]

        await _backdate_last_seen(db, minutes=31)

        assert (await _me(client, token)).status_code == 401

    async def test_activity_slides_the_window(self, client, create_user, db):
        """A request refreshes last_seen_at, so an active user is never
        logged out, the definition of an idle timeout."""
        await create_user()
        await _set_timeout(db, 30)
        token = (await _login(client)).json()["access_token"]

        await _backdate_last_seen(db, minutes=29)
        assert (await _me(client, token)).status_code == 200  # touches last_seen_at

        await _backdate_last_seen(db, minutes=2)  # 29 + 2 > 30 without the touch
        assert (await _me(client, token)).status_code == 200

    async def test_a_request_the_app_sends_on_its_own_does_not_slide_the_window(
        self, client, create_user, db
    ):
        """A poll reports that the user has been idle since before the
        session was last seen, so the timeout keeps running."""
        await create_user()
        await _set_timeout(db, 30)
        token = (await _login(client)).json()["access_token"]

        await _backdate_last_seen(db, minutes=20)
        assert (await _me(client, token, idle_seconds=20 * 60)).status_code == 200

        await _backdate_last_seen(db, minutes=31)
        assert (await _me(client, token, idle_seconds=31 * 60)).status_code == 401

    async def test_reported_activity_slides_the_window_to_when_it_happened(
        self, client, create_user, db
    ):
        await create_user()
        await _set_timeout(db, 30)
        token = (await _login(client)).json()["access_token"]
        await _backdate_last_seen(db, minutes=20)

        assert (await _me(client, token, idle_seconds=5 * 60)).status_code == 200

        idle = datetime.now(UTC) - await _last_seen(db)
        assert timedelta(minutes=4) < idle < timedelta(minutes=6)

    async def test_zero_means_sessions_never_idle_expire(self, client, create_user, db):
        await create_user()
        await _set_timeout(db, 0)
        token = (await _login(client)).json()["access_token"]

        await _backdate_last_seen(db, minutes=60 * 24 * 365)

        assert (await _me(client, token)).status_code == 200

    async def test_changing_the_setting_applies_to_existing_sessions(self, client, create_user, db):
        """The timeout is read per request, not baked in at login, so the
        admin control also applies to every already-issued token."""
        await create_user()
        await _set_timeout(db, 120)
        token = (await _login(client)).json()["access_token"]
        await _backdate_last_seen(db, minutes=31)

        assert (await _me(client, token)).status_code == 200

        await _set_timeout(db, 30)
        await _backdate_last_seen(db, minutes=31)

        assert (await _me(client, token)).status_code == 401


class TestLoginStillWorks:
    async def test_bad_credentials_still_401(self, client, create_user, db):
        await create_user()
        await _set_timeout(db, 30)

        response = await client.post(
            "/api/v1/auth/login/access-token",
            data={"username": "tester", "password": "wrong"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 401


class TestLiveStreamSessionCheck:
    """The check an open live stream runs: it follows the session row and
    never counts as activity."""

    @staticmethod
    def _check(token: str):
        request = Request({"type": "http", "headers": []})
        return get_live_session_check(request, token)

    async def test_a_live_session_answers_the_users_permissions(self, client, create_user, db):
        await create_user(permissions=["read:orders"])
        await _set_timeout(db, 30)
        token = (await _login(client)).json()["access_token"]

        assert "read:orders" in await self._check(token)()

    async def test_a_revoked_session_answers_none(self, client, create_user, db):
        await create_user()
        await _set_timeout(db, 30)
        token = (await _login(client)).json()["access_token"]
        await db.execute(text("UPDATE user_session_table SET revoked_at = CURRENT_TIMESTAMP"))
        await db.commit()

        assert await self._check(token)() is None

    async def test_the_check_does_not_slide_the_window(self, client, create_user, db):
        await create_user()
        await _set_timeout(db, 30)
        token = (await _login(client)).json()["access_token"]
        await _backdate_last_seen(db, 10)
        before = await _last_seen(db)

        assert await self._check(token)() is not None
        assert await _last_seen(db) == before
