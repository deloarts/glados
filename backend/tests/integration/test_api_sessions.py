"""
The GitHub-style sessions list at /api/v1/web/users/me/sessions: list
your own live sessions (the one making the request flagged), end one, or
end every other one, plus the sweeping revocations (self force-logout,
password change) keeping the row store honest.
"""

from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings

from .conftest import auth_headers

PASSWORD = "test-password"

SESSIONS = "/api/v1/web/users/me/sessions/"


async def _login(client, username="tester"):
    return await client.post(
        "/api/v1/auth/login/access-token",
        data={"username": username, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


async def _seed_security(db) -> None:
    """The current password of an own password change is checked through
    the login throttle, which reads the security settings."""
    await SqlAlchemyAdminSettingsRepository(db).save_security(
        AdminSecuritySettings(
            id=1,
            enforce_totp=False,
            allow_rfid_login=True,
            allow_local_login=True,
            enable_api_key_auth=False,
            min_password_length=8,
            session_timeout_minutes=1440,
            totp_trusted_device_days=0,
            max_login_attempts=5,
            lockout_duration_minutes=15,
            token_max_lifetime_days=3650,
        )
    )
    await db.commit()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestSessionsList:
    async def test_lists_own_sessions_and_flags_the_current_one(self, client, create_user, db):
        user = await create_user()
        first = await auth_headers(user)
        second = await auth_headers(user)

        response = await client.get(SESSIONS, headers=second)

        assert response.status_code == 200
        sessions = response.json()
        assert len(sessions) == 2
        assert sum(s["is_current"] for s in sessions) == 1
        # Most recently seen first; the current session was just touched.
        assert sessions[0]["is_current"] is True
        del first

    async def test_does_not_list_other_users_sessions(self, client, create_user):
        alice = await create_user(username="alice", email="alice@example.com")
        bob = await create_user(username="bob", email="bob@example.com")
        await auth_headers(alice)  # a session that must stay invisible to bob

        response = await client.get(SESSIONS, headers=await auth_headers(bob))

        assert len(response.json()) == 1  # bob's own only

    async def test_requires_auth(self, client):
        assert (await client.get(SESSIONS)).status_code == 401


class TestRevokeOne:
    async def test_revoking_another_of_my_sessions_kills_it(self, client, create_user):
        user = await create_user()
        victim = await auth_headers(user)
        acting = await auth_headers(user)

        sessions = (await client.get(SESSIONS, headers=acting)).json()
        other = next(s for s in sessions if not s["is_current"])

        assert (
            await client.delete(f"{SESSIONS}{other['public_id']}", headers=acting)
        ).status_code == 200
        # The revoked session is dead on its next request...
        assert (await client.get("/api/v1/web/users/me", headers=victim)).status_code == 401
        # ...and the acting one is untouched.
        assert (await client.get("/api/v1/web/users/me", headers=acting)).status_code == 200

    async def test_cannot_revoke_someone_elses_session(self, client, create_user):
        alice = await create_user(username="alice", email="alice@example.com")
        bob = await create_user(username="bob", email="bob@example.com")
        alice_headers = await auth_headers(alice)

        alice_sid = (await client.get(SESSIONS, headers=alice_headers)).json()[0]["public_id"]

        response = await client.delete(f"{SESSIONS}{alice_sid}", headers=await auth_headers(bob))

        assert response.status_code == 404  # indistinguishable from nonexistent
        assert (await client.get("/api/v1/web/users/me", headers=alice_headers)).status_code == 200


class TestRevokeOthers:
    async def test_signs_out_everywhere_else_but_keeps_the_current_session(
        self, client, create_user
    ):
        user = await create_user()
        other_a = await auth_headers(user)
        other_b = await auth_headers(user)
        acting = await auth_headers(user)

        response = await client.delete(SESSIONS, headers=acting)

        assert response.status_code == 200
        assert response.json()["revoked"] == 2
        assert (await client.get("/api/v1/web/users/me", headers=other_a)).status_code == 401
        assert (await client.get("/api/v1/web/users/me", headers=other_b)).status_code == 401
        assert (await client.get("/api/v1/web/users/me", headers=acting)).status_code == 200


class TestSweepingRevocations:
    async def test_self_force_logout_revokes_the_session_rows(self, client, create_user, db):
        user = await create_user()
        headers = await auth_headers(user)

        assert (
            await client.delete("/api/v1/web/users/me/session", headers=headers)
        ).status_code == 200

        live = (
            await db.execute(
                text("SELECT COUNT(*) FROM user_session_table WHERE revoked_at IS NULL")
            )
        ).scalar()
        assert live == 0

    async def test_own_password_change_keeps_current_session_kills_others(
        self, client, create_user, db
    ):
        await _seed_security(db)
        user = await create_user()
        other = await auth_headers(user)
        acting = await auth_headers(user)

        response = await client.put(
            "/api/v1/web/users/me",
            json={"password": "a-new-strong-password", "current_password": PASSWORD},
            headers=acting,
        )

        assert response.status_code == 200
        assert (await client.get("/api/v1/web/users/me", headers=other)).status_code == 401
        assert (await client.get("/api/v1/web/users/me", headers=acting)).status_code == 200


class TestOwnPasswordChangeNeedsTheCurrentOne:
    async def test_without_it_nothing_changes(self, client, create_user, db):
        await _seed_security(db)
        user = await create_user()

        response = await client.put(
            "/api/v1/web/users/me",
            json={"password": "a-new-strong-password"},
            headers=await auth_headers(user),
        )

        assert response.status_code == 422
        assert response.json()["code"] == "CurrentPasswordRequiredError"
        assert (await _login(client)).status_code == 200

    async def test_a_wrong_one_is_refused_and_counted(
        self, client, create_user, db, login_attempts
    ):
        await _seed_security(db)
        user = await create_user()

        response = await client.put(
            "/api/v1/web/users/me",
            json={"password": "a-new-strong-password", "current_password": "wrong"},
            headers=await auth_headers(user),
        )

        assert response.status_code == 400
        assert response.json()["code"] == "PasswordConfirmationFailedError"
        assert login_attempts.failures["tester|testclient"] == 1
        assert (await _login(client)).status_code == 200

    async def test_an_admin_sets_someone_elses_without_it(self, client, create_user, db):
        await _seed_security(db)
        target = await create_user()
        admin = await create_user(
            username="admin", email="admin@example.com", permissions=["write:settings"]
        )

        response = await client.put(
            f"/api/v1/web/users/{target.id}",
            json={"password": "a-new-strong-password"},
            headers=await auth_headers(admin),
        )

        assert response.status_code == 200, response.text
