"""
Administrative 2FA reset, the way back in for a user who lost their
authenticator device.

The interesting boundary is the *self* case. Force-logout lets a user act
on themselves; this deliberately does not, because self-service removal
already exists at `DELETE /users/me/totp/` and that route demands the
current TOTP code. An admin path that skipped the code would let anyone
holding a hijacked session strip their own second factor, precisely what
a session thief wants.
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
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.security.totp import generate_totp_secret
from tests.integration.conftest import _TEST_CLIENT_ADDRESS

PASSWORD = "test-password"


@pytest.fixture
def enrolled(create_user, db):
    """A user with 2FA already set up."""

    async def _make(username="victim", email="victim@example.com", **kw):
        user = await create_user(username=username, email=email, **kw)
        user.totp_secret = generate_totp_secret()
        user.totp_enabled = True
        saved = await SqlAlchemyUserRepository(db).save(user)
        await db.commit()
        return saved

    return _make


async def _reload(db, user_id):
    db.expire_all()
    return await SqlAlchemyUserRepository(db).get_by_id(user_id)


class TestResetClearsEnrolment:
    async def test_admin_can_reset_another_users_totp(self, auth_client, enrolled, db):
        target = await enrolled()
        admin = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        response = await admin.delete(f"/api/v1/web/users/{target.id}/totp")

        assert response.status_code == 200
        after = await _reload(db, target.id)
        assert after.totp_enabled is False
        assert after.totp_secret is None

    async def test_resetting_an_unenrolled_user_is_harmless(self, auth_client, create_user, db):
        target = await create_user(username="plain", email="plain@example.com")
        admin = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        assert (await admin.delete(f"/api/v1/web/users/{target.id}/totp")).status_code == 200

    async def test_unknown_user_is_404(self, auth_client):
        admin = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        assert (await admin.delete("/api/v1/web/users/999999/totp")).status_code == 404

    async def test_sessions_are_deliberately_left_alone(self, auth_client, enrolled, db):
        """Force-logout is a separate action; bundling the two would take
        the choice away from the admin."""
        target = await enrolled()
        before = target.token_version
        admin = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        await admin.delete(f"/api/v1/web/users/{target.id}/totp")

        assert (await _reload(db, target.id)).token_version == before


class TestAuthorisation:
    async def test_requires_authentication(self, client, enrolled):
        target = await enrolled()

        assert (await client.delete(f"/api/v1/web/users/{target.id}/totp")).status_code == 401

    async def test_requires_write_settings(self, auth_client, enrolled):
        target = await enrolled()
        client = await auth_client(permissions=[])

        assert (await client.delete(f"/api/v1/web/users/{target.id}/totp")).status_code == 403

    async def test_the_system_user_is_protected(self, auth_client, enrolled):
        system = await enrolled(username="system", email="system@example.com", is_systemuser=True)
        admin = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        assert (await admin.delete(f"/api/v1/web/users/{system.id}/totp")).status_code == 403

    async def test_cannot_reset_your_own(self, auth_client, create_user, db):
        """Must go through the code-confirmed self-service route instead."""
        admin_user = await create_user(
            username="admin", email="admin@example.com", permissions=[Permission.WRITE_SETTINGS]
        )
        admin_user.totp_secret = generate_totp_secret()
        admin_user.totp_enabled = True
        await SqlAlchemyUserRepository(db).save(admin_user)
        await db.commit()

        from tests.integration.conftest import auth_headers

        client = await auth_client(permissions=[])  # any client; we override the header
        client.headers.update(await auth_headers(admin_user))

        response = await client.delete(f"/api/v1/web/users/{admin_user.id}/totp")

        assert response.status_code == 403
        assert (await _reload(db, admin_user.id)).totp_enabled is True


class TestForcedReEnrolment:
    async def test_a_reset_user_is_pushed_back_through_enrolment(self, auth_client, enrolled, db):
        """With enforce_totp on, clearing the flag is all that is needed,
        the login flow picks it up with no extra wiring (step 4)."""
        target = await enrolled()
        admin = await auth_client(permissions=[Permission.WRITE_SETTINGS])

        await db.execute(text("DELETE FROM admin_security_settings"))
        await db.commit()
        await SqlAlchemyAdminSettingsRepository(db).save_security(
            AdminSecuritySettings(
                id=1,
                enforce_totp=True,
                allow_rfid_login=True,
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

        await admin.delete(f"/api/v1/web/users/{target.id}/totp")

        assert (await _reload(db, target.id)).totp_enabled is False


class TestCli:
    async def test_reset_totp_clears_enrolment(self, enrolled, db):
        from src.bootstrap.cli.admin import reset_totp

        target = await enrolled(username="alice", email="alice@example.com")

        assert await reset_totp(_Args(username="alice")) == 0

        after = await _reload(db, target.id)
        assert after.totp_enabled is False
        assert after.totp_secret is None

    async def test_unknown_username_exits_non_zero(self, db):
        from src.bootstrap.cli.admin import reset_totp

        assert await reset_totp(_Args(username="nobody")) == 1

    async def test_is_idempotent(self, create_user, db):
        from src.bootstrap.cli.admin import reset_totp

        await create_user(username="plain", email="plain@example.com")

        assert await reset_totp(_Args(username="plain")) == 0

    async def test_trusted_devices_are_revoked(self, create_user, db):
        """Mirrors ResetUserTotp (the UI's admin reset): a device trusted
        for the secret being cleared must not skip enrolment of the
        replacement. The row is seeded through the same login-with-trust
        flow test_api_trusted_devices.py uses."""
        from src.bootstrap.cli.admin import reset_totp

        secret = generate_totp_secret()
        user = await create_user(username="carol", email="carol@example.com", password=PASSWORD)
        user.totp_secret = secret
        user.totp_enabled = True
        user = await SqlAlchemyUserRepository(db).save(user)
        await db.commit()

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
                totp_trusted_device_days=30,
                max_login_attempts=0,
                lockout_duration_minutes=15,
                token_max_lifetime_days=3650,
            )
        )
        await db.commit()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=_TEST_CLIENT_ADDRESS),
            base_url="https://testserver",
            follow_redirects=True,
        ) as https_client:
            challenge = (
                await https_client.post(
                    "/api/v1/auth/login/access-token",
                    data={"username": "carol", "password": PASSWORD},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            ).json()
            login = await https_client.post(
                "/api/v1/auth/login/totp",
                json={
                    "partial_token": challenge["partial_token"],
                    "totp_code": pyotp.TOTP(secret).now(),
                    "trust_device": True,
                },
            )
        assert login.status_code == 200

        async def _live_devices() -> int:
            return (
                await db.execute(
                    text(
                        "SELECT COUNT(*) FROM user_trusted_device_table "
                        "WHERE user_id = :uid AND revoked_at IS NULL"
                    ),
                    {"uid": user.id},
                )
            ).scalar()

        assert await _live_devices() == 1

        assert await reset_totp(_Args(username="carol")) == 0

        assert await _live_devices() == 0


class _Args:
    def __init__(self, username: str) -> None:
        self.username = username
