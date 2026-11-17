"""
`enforce_totp`, mandatory 2FA with enrolment forced at login.

Chosen behaviour: a user who has not enrolled is **let in far enough to
enrol** rather than refused outright. Refusing would lock out every member
of staff the instant an admin flips the switch.

The security of the whole thing rests on the setup token being useless for
anything except enrolment, so that is what most of these cover. The scope
is allowlisted in ValidateWebToken (see token_scope.py), which means it is
refused on every route that has not explicitly opted in, the tests below
sample that, but the allowlist is what makes it true in general.
"""

import pyotp
import pytest
from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.security.totp import generate_totp_secret
from tests.factories import TEST_PASSWORD

PASSWORD = "test-password"


async def _set_enforce_totp(db, enabled: bool) -> None:
    await db.execute(text("DELETE FROM admin_security_settings"))
    await db.commit()
    await SqlAlchemyAdminSettingsRepository(db).save_security(
        AdminSecuritySettings(
            id=1,
            enforce_totp=enabled,
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


async def _login(client, username="tester"):
    return await client.post(
        "/api/v1/auth/login/access-token",
        data={"username": username, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def forced(client, create_user, db):
    """A user who must enrol, and their setup token."""
    await create_user()
    await _set_enforce_totp(db, True)
    return (await _login(client)).json()


# ── The login outcome ─────────────────────────────────────────────────


class TestLoginIssuesASetupChallenge:
    def test_unenrolled_user_gets_a_setup_challenge(self, forced):
        assert forced["totp_setup_required"] is True
        assert forced["setup_token"]

    def test_no_session_token_is_issued(self, forced):
        """The user is not logged in yet, only allowed to enrol."""
        assert "access_token" not in forced

    def test_the_username_is_included(self, forced):
        """The enrolment screen cannot call /users/me with a setup token,
        so it has nothing to display unless login provides it."""
        assert forced["username"] == "tester"

    async def test_an_enrolled_user_still_gets_the_normal_code_challenge(
        self, client, create_user, db
    ):
        user = await create_user()
        user.totp_secret = generate_totp_secret()
        user.totp_enabled = True
        await SqlAlchemyUserRepository(db).save(user)
        await db.commit()
        await _set_enforce_totp(db, True)

        body = (await _login(client)).json()

        assert body.get("totp_required") is True
        assert "partial_token" in body

    async def test_without_enforcement_login_is_unchanged(self, client, create_user, db):
        await create_user()
        await _set_enforce_totp(db, False)

        body = (await _login(client)).json()

        assert "access_token" in body
        assert "totp_setup_required" not in body


# ── Completing the ordinary (already-enrolled) 2FA challenge ──────────
#
# Distinct from TestConfirmCompletesTheFlow below, which completes a
# forced *enrolment*. This is the everyday path: a user who already has
# 2FA set up, submitting the code at their next login.


class TestOrdinaryTotpLoginStep:
    async def _challenge(self, client, create_user, db):
        user = await create_user()
        secret = generate_totp_secret()
        user.totp_secret = secret
        user.totp_enabled = True
        await SqlAlchemyUserRepository(db).save(user)
        await db.commit()
        await _set_enforce_totp(db, True)

        partial_token = (await _login(client)).json()["partial_token"]
        return partial_token, secret

    async def test_the_correct_code_issues_a_session(self, client, create_user, db):
        partial_token, secret = await self._challenge(client, create_user, db)

        response = await client.post(
            "/api/v1/auth/login/totp",
            json={"partial_token": partial_token, "totp_code": pyotp.TOTP(secret).now()},
        )

        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_a_wrong_code_is_rejected_with_a_stable_error_code(self, client, create_user, db):
        partial_token, secret = await self._challenge(client, create_user, db)
        wrong_code = "000000" if pyotp.TOTP(secret).now() != "000000" else "111111"

        response = await client.post(
            "/api/v1/auth/login/totp",
            json={"partial_token": partial_token, "totp_code": wrong_code},
        )

        assert response.status_code == 401
        # Still-live challenge, just a wrong code, the frontend lets the
        # user retry in place rather than bouncing them back to credentials.
        # Contrast TestSetupTokenIsRestricted's
        # test_it_cannot_be_redeemed_at_the_totp_login_step below, which
        # gets TOTPChallengeInvalidError instead.
        assert response.json()["code"] == "InvalidTOTPCodeError"


# ── The setup token is good for enrolment only ────────────────────────


class TestSetupTokenIsRestricted:
    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/api/v1/web/users/me"),
            ("GET", "/api/v1/web/users/"),
            ("GET", "/api/v1/web/customers/"),
            ("GET", "/api/v1/web/projects/"),
        ],
    )
    async def test_it_is_refused_on_ordinary_routes(self, client, forced, method, path):
        response = await client.request(method, path, headers=_auth(forced["setup_token"]))

        assert response.status_code == 401

    async def test_it_is_accepted_by_enroll(self, client, forced):
        response = await client.post(
            "/api/v1/web/users/me/totp/enroll", headers=_auth(forced["setup_token"])
        )

        assert response.status_code == 200
        assert response.json()["secret"]

    async def test_it_cannot_be_redeemed_at_the_totp_login_step(self, client, forced):
        """Different scope, a setup token must not stand in for the
        totp_pending challenge."""
        response = await client.post(
            "/api/v1/auth/login/totp",
            json={"partial_token": forced["setup_token"], "totp_code": "000000"},
        )

        assert response.status_code == 401
        # Distinct from a wrong code (InvalidTOTPCodeError): the frontend
        # sends the user back to the credentials form for this one instead
        # of letting them retry the code, see authStore.submitTotp.
        assert response.json()["code"] == "TOTPChallengeInvalidError"


# ── Completing enrolment ──────────────────────────────────────────────


class TestConfirmCompletesTheFlow:
    async def _enrol(self, client, forced):
        secret = (
            await client.post(
                "/api/v1/web/users/me/totp/enroll", headers=_auth(forced["setup_token"])
            )
        ).json()["secret"]
        return await client.post(
            "/api/v1/web/users/me/totp/confirm",
            json={"totp_code": pyotp.TOTP(secret).now()},
            headers=_auth(forced["setup_token"]),
        )

    async def test_confirm_returns_a_real_session(self, client, forced):
        """Otherwise the user would have to log in again and type a second
        code seconds after the first."""
        response = await self._enrol(client, forced)

        assert response.status_code == 200
        assert response.json()["access_token"]
        assert response.json()["token_type"] == "bearer"

    async def test_that_session_works_on_ordinary_routes(self, client, forced):
        token = (await self._enrol(client, forced)).json()["access_token"]

        response = await client.get("/api/v1/web/users/me", headers=_auth(token))

        assert response.status_code == 200
        assert response.json()["username"] == "tester"

    async def test_2fa_is_now_enabled(self, client, forced, db):
        await self._enrol(client, forced)

        db.expire_all()
        user = await SqlAlchemyUserRepository(db).get_by_username("tester")
        assert user is not None
        assert user.totp_enabled is True

    async def test_the_next_login_takes_the_normal_2fa_path(self, client, forced):
        await self._enrol(client, forced)

        body = (await _login(client)).json()

        assert body.get("totp_required") is True
        assert "totp_setup_required" not in body

    async def test_a_wrong_code_does_not_complete_enrolment(self, client, forced):
        await client.post("/api/v1/web/users/me/totp/enroll", headers=_auth(forced["setup_token"]))

        response = await client.post(
            "/api/v1/web/users/me/totp/confirm",
            json={"totp_code": "000000"},
            headers=_auth(forced["setup_token"]),
        )

        assert response.status_code == 401
        # Propagated from the domain exception rather than a hand-rolled
        # HTTPException, so the client gets a stable `code` to key off.
        assert response.json()["code"] == "InvalidTOTPCodeError"

    async def test_abandoning_and_restarting_enrolment_works(self, client, forced):
        """A user who closes the tab mid-enrolment must not be stranded by
        the stale secret from the first attempt."""
        await client.post("/api/v1/web/users/me/totp/enroll", headers=_auth(forced["setup_token"]))
        second = (
            await client.post(
                "/api/v1/web/users/me/totp/enroll", headers=_auth(forced["setup_token"])
            )
        ).json()["secret"]

        response = await client.post(
            "/api/v1/web/users/me/totp/confirm",
            json={"totp_code": pyotp.TOTP(second).now()},
            headers=_auth(forced["setup_token"]),
        )

        assert response.status_code == 200


# ── Voluntary enrolment is unchanged ──────────────────────────────────


class TestVoluntaryEnrolmentStillWorks:
    async def test_a_normal_session_can_still_enrol_and_gets_no_token_back(self, auth_client, db):
        await _set_enforce_totp(db, False)
        client = await auth_client()

        enrolled = await client.post(
            "/api/v1/web/users/me/totp/enroll", json={"password": TEST_PASSWORD}
        )
        secret = enrolled.json()["secret"]
        response = await client.post(
            "/api/v1/web/users/me/totp/confirm", json={"totp_code": pyotp.TOTP(secret).now()}
        )

        assert response.status_code == 200
        assert response.json()["detail"] == "2FA enabled"
        assert response.json()["access_token"] is None


# ── Step 5: admins need 2FA even without global enforcement ───────────


class TestWriteSettingsHoldersMustEnrol:
    async def test_an_admin_is_forced_to_enrol_without_global_enforcement(
        self, client, create_user, db
    ):
        await create_user(
            username="admin", email="admin@example.com", permissions=[Permission.WRITE_SETTINGS]
        )
        await _set_enforce_totp(db, False)

        body = (await _login(client, username="admin")).json()

        assert body.get("totp_setup_required") is True

    async def test_an_ordinary_user_is_not(self, client, create_user, db):
        await create_user(
            username="plain", email="plain@example.com", permissions=[Permission.WRITE_PROJECTS]
        )
        await _set_enforce_totp(db, False)

        body = (await _login(client, username="plain")).json()

        assert "access_token" in body

    async def test_the_admin_can_complete_enrolment_and_get_a_session(
        self, client, create_user, db
    ):
        await create_user(
            username="admin", email="admin@example.com", permissions=[Permission.WRITE_SETTINGS]
        )
        await _set_enforce_totp(db, False)
        forced = (await _login(client, username="admin")).json()

        secret = (
            await client.post(
                "/api/v1/web/users/me/totp/enroll", headers=_auth(forced["setup_token"])
            )
        ).json()["secret"]
        confirmed = await client.post(
            "/api/v1/web/users/me/totp/confirm",
            json={"totp_code": pyotp.TOTP(secret).now()},
            headers=_auth(forced["setup_token"]),
        )

        assert confirmed.status_code == 200
        assert confirmed.json()["access_token"]

    async def test_the_system_user_is_always_forced(self, client, create_user, db):
        """Hardening: the system account is not exempt from 2FA (see
        login_policy.totp_enrolment_required), `admin reset-totp` (CLI) is
        the recovery path, not a login-time bypass. Deeper coverage of
        the system-user hardening lives in
        test_api_system_user_hardening.py."""
        await create_user(username="system", email="system@example.com", is_systemuser=True)
        await _set_enforce_totp(db, True)

        body = (await _login(client, username="system")).json()

        assert body.get("totp_setup_required") is True
        assert "access_token" not in body


# ── Users who have been force-logged-out ──────────────────────────────


class TestNonZeroTokenVersion:
    """Every fixture user starts at token_version 0, which would hide a
    setup token without a `ver` claim: ValidateWebToken would read it as 0
    and reject anyone who had ever been force-logged-out with "Session
    invalidated". These users start at a higher version instead.
    """

    @pytest.fixture
    async def bumped(self, client, create_user, db):
        user = await create_user()
        user.token_version = 3  # as if force-logged-out a few times
        await SqlAlchemyUserRepository(db).save(user)
        await db.commit()
        await _set_enforce_totp(db, True)
        return (await _login(client)).json()

    def test_login_still_issues_a_setup_challenge(self, bumped):
        assert bumped["totp_setup_required"] is True

    async def test_the_setup_token_is_accepted_by_enroll(self, client, bumped):
        response = await client.post(
            "/api/v1/web/users/me/totp/enroll", headers=_auth(bumped["setup_token"])
        )

        assert response.status_code == 200, response.text
        assert response.json()["secret"]

    async def test_the_whole_flow_completes(self, client, bumped):
        secret = (
            await client.post(
                "/api/v1/web/users/me/totp/enroll", headers=_auth(bumped["setup_token"])
            )
        ).json()["secret"]

        confirmed = await client.post(
            "/api/v1/web/users/me/totp/confirm",
            json={"totp_code": pyotp.TOTP(secret).now()},
            headers=_auth(bumped["setup_token"]),
        )

        assert confirmed.status_code == 200
        assert confirmed.json()["access_token"]

    async def test_a_stale_version_is_still_rejected(self, client, create_user, db):
        """The version check still applies: a setup token minted before a
        force-logout is no longer accepted."""
        user = await create_user()
        await _set_enforce_totp(db, True)
        stale = (await _login(client)).json()["setup_token"]

        user.token_version += 1
        await SqlAlchemyUserRepository(db).save(user)
        await db.commit()

        response = await client.post("/api/v1/web/users/me/totp/enroll", headers=_auth(stale))

        assert response.status_code == 401
