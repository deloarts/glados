"""
"Trust this device" end to end: opting in at the TOTP step sets an
httpOnly cookie whose (hashed) secret is a server-side row; the next
password login skips the TOTP challenge entirely while the row is live.
Revocation sweeps, password change, TOTP disable, admin TOTP reset:
must put the prompt back.

Clients here use an https base_url: the cookie is Secure outside debug
mode, and httpx's jar (correctly) refuses to send Secure cookies over
plain http.
"""

import httpx
import pyotp
import pytest
from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.infrastructure.security.totp import generate_totp_secret

from .conftest import _TEST_CLIENT_ADDRESS
from .conftest import auth_headers

PASSWORD = "test-password"

DEVICES = "/api/v1/web/users/me/trusted-devices/"
COOKIE = "glados_trusted_device"


@pytest.fixture
async def https_client():
    """Cookie-carrying client. https so the Secure cookie flows back."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=_TEST_CLIENT_ADDRESS),
        base_url="https://testserver",
        follow_redirects=True,
    ) as client:
        yield client


async def _seed_security(db, trust_days: int = 30) -> None:
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
            session_timeout_minutes=0,
            totp_trusted_device_days=trust_days,
            max_login_attempts=0,
            lockout_duration_minutes=15,
            token_max_lifetime_days=3650,
        )
    )
    await db.commit()


@pytest.fixture
def enrolled(create_user, db):
    """A user with 2FA already set up. Returns (user, secret)."""

    async def _make(username="tester", email="tester@example.com", **kw):
        user = await create_user(username=username, email=email, password=PASSWORD, **kw)
        secret = generate_totp_secret()
        user.totp_secret = secret
        user.totp_enabled = True
        saved = await SqlAlchemyUserRepository(db).save(user)
        await db.commit()
        return saved, secret

    return _make


async def _password_login(client, username="tester"):
    return await client.post(
        "/api/v1/auth/login/access-token",
        data={"username": username, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


async def _full_login_with_trust(client, secret: str, *, trust: bool, username: str = "tester"):
    """Password step, then the TOTP step with the trust checkbox state."""
    challenge = (await _password_login(client, username=username)).json()
    assert "partial_token" in challenge, f"expected a TOTP challenge, got {challenge}"
    return await client.post(
        "/api/v1/auth/login/totp",
        json={
            "partial_token": challenge["partial_token"],
            "totp_code": pyotp.TOTP(secret).now(),
            "trust_device": trust,
        },
    )


class TestTrustGrant:
    async def test_challenge_advertises_the_configured_trust_days(self, https_client, enrolled, db):
        await enrolled()
        await _seed_security(db, trust_days=14)

        assert (await _password_login(https_client)).json()["trusted_device_days"] == 14

    async def test_opting_in_sets_the_cookie_and_the_row(self, https_client, enrolled, db):
        _, secret = await enrolled()
        await _seed_security(db)

        response = await _full_login_with_trust(https_client, secret, trust=True)

        assert response.status_code == 200
        assert COOKIE in https_client.cookies
        assert (
            await db.execute(text("SELECT COUNT(*) FROM user_trusted_device_table"))
        ).scalar() == 1
        # Only the hash is stored, never the cookie value itself.
        stored = (
            await db.execute(text("SELECT token_hash FROM user_trusted_device_table"))
        ).scalar()
        assert stored != https_client.cookies[COOKIE]

    async def test_the_cookie_is_httponly_and_path_scoped(self, https_client, enrolled, db):
        _, secret = await enrolled()
        await _seed_security(db)

        response = await _full_login_with_trust(https_client, secret, trust=True)

        set_cookie = response.headers["set-cookie"]
        assert "HttpOnly" in set_cookie
        assert "Path=/api/v1/auth" in set_cookie

    async def test_not_opting_in_sets_nothing(self, https_client, enrolled, db):
        _, secret = await enrolled()
        await _seed_security(db)

        await _full_login_with_trust(https_client, secret, trust=False)

        assert COOKIE not in https_client.cookies

    async def test_disabled_setting_ignores_the_flag_and_hides_the_offer(
        self, https_client, enrolled, db
    ):
        _, secret = await enrolled()
        await _seed_security(db, trust_days=0)

        assert (await _password_login(https_client)).json()["trusted_device_days"] == 0
        await _full_login_with_trust(https_client, secret, trust=True)

        assert COOKIE not in https_client.cookies


class TestTrustedLogin:
    async def test_second_login_skips_the_totp_challenge(self, https_client, enrolled, db):
        _, secret = await enrolled()
        await _seed_security(db)
        await _full_login_with_trust(https_client, secret, trust=True)

        second = (await _password_login(https_client)).json()

        assert "access_token" in second
        assert "partial_token" not in second

    async def test_the_skipped_login_yields_a_working_session(self, https_client, enrolled, db):
        _, secret = await enrolled()
        await _seed_security(db)
        await _full_login_with_trust(https_client, secret, trust=True)

        token = (await _password_login(https_client)).json()["access_token"]
        me = await https_client.get(
            "/api/v1/web/users/me", headers={"Authorization": f"Bearer {token}"}
        )

        assert me.status_code == 200

    async def test_trust_is_per_user(self, https_client, enrolled, db):
        """Alice's cookie must not skip Bob's TOTP."""
        _, alice_secret = await enrolled(username="alice", email="alice@example.com")
        await enrolled(username="bob", email="bob@example.com")
        await _seed_security(db)
        await _full_login_with_trust(https_client, alice_secret, trust=True, username="alice")

        bob_login = (await _password_login(https_client, username="bob")).json()

        assert "partial_token" in bob_login

    async def test_an_expired_grant_prompts_again(self, https_client, enrolled, db):
        _, secret = await enrolled()
        await _seed_security(db)
        await _full_login_with_trust(https_client, secret, trust=True)

        await db.execute(
            text("UPDATE user_trusted_device_table SET expires_at = '2020-01-01 00:00:00'")
        )
        await db.commit()

        assert "partial_token" in (await _password_login(https_client)).json()


class TestRevocationSweeps:
    async def _trusted(self, https_client, enrolled, db):
        user, secret = await enrolled()
        await _seed_security(db)
        await _full_login_with_trust(https_client, secret, trust=True)
        return user, secret

    async def test_password_change_revokes_trust(self, https_client, enrolled, db):
        user, _ = await self._trusted(https_client, enrolled, db)

        response = await https_client.put(
            "/api/v1/web/users/me",
            json={"password": "a-new-strong-password", "current_password": PASSWORD},
            headers=await auth_headers(user),
        )
        assert response.status_code == 200

        # Cookie still in the jar, but the row is revoked, prompt returns.
        challenge = (
            await https_client.post(
                "/api/v1/auth/login/access-token",
                data={"username": "tester", "password": "a-new-strong-password"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        ).json()
        assert "partial_token" in challenge

    async def test_totp_disable_revokes_trust(self, https_client, enrolled, db):
        user, secret = await self._trusted(https_client, enrolled, db)

        response = await https_client.request(
            "DELETE",
            "/api/v1/web/users/me/totp/",
            json={"totp_code": pyotp.TOTP(secret).now()},
            headers=await auth_headers(user),
        )
        assert response.status_code == 200

        live = (
            await db.execute(
                text("SELECT COUNT(*) FROM user_trusted_device_table WHERE revoked_at IS NULL")
            )
        ).scalar()
        assert live == 0

    async def test_admin_totp_reset_revokes_trust(self, https_client, enrolled, db, create_user):
        user, _ = await self._trusted(https_client, enrolled, db)
        admin = await create_user(
            username="admin", email="admin@example.com", permissions=["write:settings"]
        )

        response = await https_client.delete(
            f"/api/v1/web/users/{user.id}/totp", headers=await auth_headers(admin)
        )
        assert response.status_code == 200

        live = (
            await db.execute(
                text("SELECT COUNT(*) FROM user_trusted_device_table WHERE revoked_at IS NULL")
            )
        ).scalar()
        assert live == 0


class TestSelfService:
    async def test_lists_and_revokes_own_grants(self, https_client, enrolled, db):
        user, secret = await enrolled()
        await _seed_security(db)
        await _full_login_with_trust(https_client, secret, trust=True)
        headers = await auth_headers(user)

        devices = (await https_client.get(DEVICES, headers=headers)).json()
        assert len(devices) == 1

        assert (
            await https_client.delete(f"{DEVICES}{devices[0]['public_id']}", headers=headers)
        ).status_code == 200
        assert (await https_client.get(DEVICES, headers=headers)).json() == []
        # And the skip is gone.
        assert "partial_token" in (await _password_login(https_client)).json()
