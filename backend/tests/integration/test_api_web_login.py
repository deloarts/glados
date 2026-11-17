"""
End-to-end coverage of POST /api/v1/auth/login/access-token.

This endpoint had no direct test of its own: the OAuth2 form parsing, the
401/403 split, the allow_local_login gate and the TOTP branch were only ever
exercised incidentally. Everything here is the *local* half, the directory
cases live in test_api_web_login_ldap.py.
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

PASSWORD = "test-password"
LOGIN_URL = "/api/v1/auth/login/access-token"


async def login(client, username="tester", password=PASSWORD):
    return await client.post(
        LOGIN_URL,
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


@pytest.fixture
async def relaxed_security(db):
    """enforce_totp defaults to on for write:settings holders; these tests
    care about the credential path, not enrolment."""
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
            totp_trusted_device_days=0,
            max_login_attempts=0,
            lockout_duration_minutes=15,
            token_max_lifetime_days=3650,
        )
    )
    await db.commit()


# ── Success ───────────────────────────────────────────────────────────


class TestSuccessfulLogin:
    @pytest.mark.smoke
    async def test_correct_username_and_password_returns_a_bearer_token(
        self, client, create_user, relaxed_security
    ):
        await create_user()
        response = await login(client)

        assert response.status_code == 200
        assert response.json()["token_type"] == "bearer"
        assert response.json()["access_token"]

    async def test_the_token_works_on_a_protected_route(
        self, client, create_user, relaxed_security
    ):
        await create_user()
        token = (await login(client)).json()["access_token"]

        me = await client.get("/api/v1/web/users/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["username"] == "tester"

    async def test_last_logged_in_is_stamped(self, client, create_user, db, relaxed_security):
        user = await create_user()
        assert user.last_logged_in is None

        await login(client)

        db.expire_all()
        assert (await SqlAlchemyUserRepository(db).get_by_id(user.id)).last_logged_in is not None


# ── Identifier resolution ─────────────────────────────────────────────


class TestIdentifierResolution:
    """The identifier may be a username or an e-mail, matched
    case-insensitively, AD's sAMAccountName is case-insensitive, so an exact
    match would reject a user whose directory login works as "Mock"."""

    async def test_email_works_as_the_identifier(self, client, create_user, relaxed_security):
        await create_user(username="alice", email="alice@corp.example")

        assert (await login(client, username="alice@corp.example")).status_code == 200

    async def test_username_is_case_insensitive(self, client, create_user, relaxed_security):
        await create_user(username="alice", email="alice@corp.example")

        assert (await login(client, username="ALICE")).status_code == 200

    async def test_email_is_case_insensitive(self, client, create_user, relaxed_security):
        await create_user(username="alice", email="alice@corp.example")

        assert (await login(client, username="Alice@Corp.Example")).status_code == 200

    async def test_surrounding_whitespace_is_ignored(self, client, create_user, relaxed_security):
        await create_user(username="alice", email="alice@corp.example")

        assert (await login(client, username="  alice  ")).status_code == 200


# ── Rejection ─────────────────────────────────────────────────────────


class TestRejection:
    @pytest.mark.smoke
    async def test_wrong_password_is_401(self, client, create_user, relaxed_security):
        await create_user()
        assert (await login(client, password="wrong")).status_code == 401

    async def test_unknown_identifier_is_401(self, client, create_user, relaxed_security):
        await create_user()
        assert (await login(client, username="nobody")).status_code == 401

    async def test_empty_password_is_rejected(self, client, create_user, relaxed_security):
        """python-multipart >= 0.0.32 drops empty form fields, so an empty
        password arrives as a missing field and is rejected by request
        validation (422) before authentication runs."""
        await create_user()
        resp = await login(client, password="")
        assert resp.status_code == 422

    async def test_inactive_account_is_403(self, client, create_user, relaxed_security):
        await create_user(is_active=False)
        assert (await login(client)).status_code == 403

    async def test_inactive_account_with_a_wrong_password_is_still_401(
        self, client, create_user, relaxed_security
    ):
        """Credentials are judged before the active check, so a wrong password
        must not reveal that the account exists but is disabled."""
        await create_user(is_active=False)
        assert (await login(client, password="wrong")).status_code == 401

    async def test_service_account_cannot_log_in(self, client, create_user, relaxed_security):
        """Service accounts are API-key identities, never interactive."""
        await create_user(is_service_account=True)
        assert (await login(client)).status_code == 401

    async def test_the_error_detail_does_not_distinguish_the_two_failures(
        self, client, create_user, relaxed_security
    ):
        await create_user()
        unknown = (await login(client, username="nobody")).json()["detail"]
        wrong = (await login(client, password="wrong")).json()["detail"]

        assert unknown == wrong


# ── Unusable local hash ───────────────────────────────────────────────


class TestUnusableLocalHash:
    async def test_a_placeholder_hash_is_401_not_500(
        self, client, create_user, db, relaxed_security
    ):
        """hashed_password is NOT NULL but nothing guarantees a real bcrypt
        digest; checkpw raises ValueError on one, which would otherwise
        surface as an unhandled 500 on a public endpoint."""
        user = await create_user()
        await db.execute(
            text("UPDATE user_table SET hashed_password = :h WHERE id = :i"),
            {"h": "not-a-bcrypt-hash", "i": user.id},
        )
        await db.commit()

        assert (await login(client)).status_code == 401


class TestPasswordPastBcryptsInputLimit:
    """bcrypt reads only the first 72 bytes. bcrypt 5 raises on longer input
    where bcrypt 4 dropped the rest, and the login path answers a raise with
    401, so without the cut in hashing.py a long password would silently stop
    working after the upgrade."""

    LONG = "a" * 72 + "suffix12"
    # LONG hashed by bcrypt 4.3.0 (cost 4), as a row stored before the upgrade.
    LONG_BCRYPT4 = "$2b$04$2kV8yDSAEL24GYkMCbLMqua4lAYb1my6n9GwCmcv41aWXEu8ktSqO"

    async def test_a_password_over_72_bytes_logs_in(self, client, create_user, relaxed_security):
        await create_user(password=self.LONG)

        assert (await login(client, password=self.LONG)).status_code == 200

    async def test_a_long_password_stored_by_bcrypt_4_still_logs_in(
        self, client, create_user, db, relaxed_security
    ):
        user = await create_user()
        await db.execute(
            text("UPDATE user_table SET hashed_password = :h WHERE id = :i"),
            {"h": self.LONG_BCRYPT4, "i": user.id},
        )
        await db.commit()

        assert (await login(client, password=self.LONG)).status_code == 200
