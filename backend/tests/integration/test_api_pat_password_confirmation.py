"""
The self-service changes that would turn a session into lasting access ask
for the current password again: creating a personal access token and
setting up 2FA from a session. A changed password revokes the account's
tokens, so changing it recovers an account whose password was known to
someone else.
"""

from typing import Any

import pytest
from sqlalchemy import text

from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import TEST_PASSWORD

PATS = "/api/v1/web/users/me/personal-access-tokens/"
ENROLL = "/api/v1/web/users/me/totp/enroll"


@pytest.fixture
async def owner(auth_client, seeded_security) -> Any:
    return await auth_client(permissions=[Permission.WRITE_PAT])


async def _token_count(db) -> int:
    return int((await db.execute(text("SELECT COUNT(*) FROM pat_table"))).scalar_one())


class TestCreatingAToken:
    async def test_without_the_password_is_refused(self, owner, db) -> None:
        response = await owner.post(PATS, json={"name": "CI"})

        assert response.status_code == 422, response.text
        assert await _token_count(db) == 0

    async def test_with_a_wrong_password_is_refused_and_counted(
        self, owner, db, login_attempts
    ) -> None:
        response = await owner.post(PATS, json={"name": "CI", "password": "wrong"})

        assert response.status_code == 400, response.text
        assert response.json()["code"] == "PasswordConfirmationFailedError"
        assert login_attempts.failures["tester|testclient"] == 1
        assert await _token_count(db) == 0

    async def test_with_the_password_succeeds(self, owner, db) -> None:
        response = await owner.post(PATS, json={"name": "CI", "password": TEST_PASSWORD})

        assert response.status_code == 201, response.text
        assert await _token_count(db) == 1


class TestChangingThePassword:
    async def test_revokes_every_token_of_the_account(self, owner, client) -> None:
        created = await owner.post(PATS, json={"name": "CI", "password": TEST_PASSWORD})
        token = created.json()["token"]
        assert (
            await client.get("/api/v1/pat/users/me", headers={"X-Api-Key": token})
        ).status_code == 200

        changed = await owner.put(
            "/api/v1/web/users/me",
            json={"password": "a-new-strong-password", "current_password": TEST_PASSWORD},
        )

        assert changed.status_code == 200, changed.text
        assert (
            await client.get("/api/v1/pat/users/me", headers={"X-Api-Key": token})
        ).status_code == 401


class TestSettingUp2faFromASession:
    async def test_without_the_password_is_refused(self, owner) -> None:
        response = await owner.post(ENROLL)

        assert response.status_code == 422, response.text
        assert response.json()["code"] == "CurrentPasswordRequiredError"

    async def test_with_a_wrong_password_is_refused(self, owner) -> None:
        response = await owner.post(ENROLL, json={"password": "wrong"})

        assert response.status_code == 400, response.text
        assert response.json()["code"] == "PasswordConfirmationFailedError"

    async def test_with_the_password_returns_a_secret(self, owner) -> None:
        response = await owner.post(ENROLL, json={"password": TEST_PASSWORD})

        assert response.status_code == 200, response.text
        assert response.json()["secret"]
