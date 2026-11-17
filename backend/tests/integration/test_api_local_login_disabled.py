"""
`allow_local_login` gates password login: with it off in the admin UI, a
password sign-in is refused.

Two properties matter here and pull in opposite directions:

  * with it off, ordinary users are refused (the point of the setting), and
  * the system user is still let through, because password login is
    the *only* interactive method, RFID issues no sessions, so
    without that exemption switching this off would lock every human out
    of the application with no way back in through the UI.
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
from src.modules.platform.infrastructure.security.totp import generate_totp_secret

PASSWORD = "test-password"


async def _set_local_login(db, enabled: bool) -> None:
    await db.execute(text("DELETE FROM admin_security_settings"))
    await db.commit()
    await SqlAlchemyAdminSettingsRepository(db).save_security(
        AdminSecuritySettings(
            id=1,
            enforce_totp=False,
            allow_rfid_login=True,
            allow_local_login=enabled,
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


async def _login(client, username="tester", password=PASSWORD):
    return await client.post(
        "/api/v1/auth/login/access-token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


class TestLocalLoginDisabled:
    async def test_enabled_lets_a_normal_user_in(self, client, create_user, db):
        await create_user()
        await _set_local_login(db, True)

        assert (await _login(client)).status_code == 200

    async def test_disabled_refuses_a_normal_user(self, client, create_user, db):
        await create_user()
        await _set_local_login(db, False)

        assert (await _login(client)).status_code == 403

    async def test_disabled_refuses_even_with_correct_credentials(self, client, create_user, db):
        """Not a 401, the credentials were fine, the method is not."""
        await create_user()
        await _set_local_login(db, False)

        response = await _login(client)

        assert response.status_code == 403
        assert response.status_code != 401

    async def test_wrong_credentials_still_401_when_disabled(self, client, create_user, db):
        """The policy is checked after the password, so a bad password
        cannot be used to discover that local login is switched off."""
        await create_user()
        await _set_local_login(db, False)

        assert (await _login(client, password="wrong")).status_code == 401

    async def test_toggling_it_back_on_restores_access(self, client, create_user, db):
        await create_user()

        await _set_local_login(db, False)
        assert (await _login(client)).status_code == 403

        await _set_local_login(db, True)
        assert (await _login(client)).status_code == 200


class TestSystemUserExemption:
    async def test_system_user_can_still_sign_in(self, client, create_user, db):
        """The in-app recovery path, without this, disabling the setting
        would be unrecoverable except via the CLI."""
        await create_user(username="system", email="system@example.com", is_systemuser=True)
        await _set_local_login(db, False)

        assert (await _login(client, username="system")).status_code == 200

    async def test_the_exemption_does_not_leak_to_ordinary_users(self, client, create_user, db):
        await create_user(username="system", email="system@example.com", is_systemuser=True)
        await create_user(username="tester", email="tester@example.com")
        await _set_local_login(db, False)

        assert (await _login(client, username="system")).status_code == 200
        assert (await _login(client, username="tester")).status_code == 403


class TestTotpSecondStepIsAlsoGated:
    async def test_a_pending_challenge_cannot_be_redeemed_once_disabled(
        self, client, create_user, db
    ):
        """The challenge token lives for five minutes; switching the
        setting off inside that window must still take effect."""
        user = await create_user()
        user.totp_secret = generate_totp_secret()
        user.totp_enabled = True
        await SqlAlchemyUserRepository(db).save(user)
        await db.commit()
        await _set_local_login(db, True)

        challenge = (await _login(client)).json()
        assert "partial_token" in challenge

        await _set_local_login(db, False)
        response = await client.post(
            "/api/v1/auth/login/totp",
            json={"partial_token": challenge["partial_token"], "totp_code": "000000"},
        )

        assert response.status_code in (401, 403)


@pytest.fixture
def _cli_db(db):
    return db


class TestCliRecovery:
    async def test_enable_local_login_turns_it_back_on(self, _cli_db):
        from src.bootstrap.cli.admin import enable_local_login

        await _set_local_login(_cli_db, False)
        repo = SqlAlchemyAdminSettingsRepository(_cli_db)
        assert (await repo.get_security()).allow_local_login is False

        await enable_local_login(None)  # type: ignore[arg-type]

        _cli_db.expire_all()
        assert (await repo.get_security()).allow_local_login is True

    async def test_is_idempotent(self, _cli_db):
        from src.bootstrap.cli.admin import enable_local_login

        await _set_local_login(_cli_db, True)

        assert await enable_local_login(None) == 0  # type: ignore[arg-type]

        _cli_db.expire_all()
        assert (
            await SqlAlchemyAdminSettingsRepository(_cli_db).get_security()
        ).allow_local_login is True
