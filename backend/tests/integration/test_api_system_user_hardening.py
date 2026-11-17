"""
End-to-end coverage for the `system` account hardening: mandatory 2FA with
no exemption (login_policy.totp_enrolment_required), a 15-minute hard
session lifetime on top of the idle timeout (session_rules.py,
ValidateWebToken._check_session), no "trust this device"
(effective_trusted_device_days), no personal access tokens, ever
(PatRules.assert_can_create / ValidatePat), and the countdown's data
source (GET /users/me/sessions/current).

Each property is exercised at the HTTP layer against the real SQLAlchemy
repositories (throwaway SQLite, see tests/integration/conftest.py), the
same pattern as test_api_forced_totp_enrolment.py and
test_api_session_timeout.py.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

import jwt
import pyotp
import pytest
from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.entities.personal_access_token import PersonalAccessToken
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.security.pat import display_prefix
from src.modules.platform.infrastructure.security.pat import hash_pat
from src.modules.platform.infrastructure.security.totp import generate_totp_secret
from src.modules.platform.infrastructure.security.trusted_device import TRUSTED_DEVICE_COOKIE
from tests.factories import TEST_PASSWORD

PASSWORD = "test-password"


async def _set_security(db, **overrides) -> None:
    await db.execute(text("DELETE FROM admin_security_settings"))
    await db.commit()
    defaults = dict(
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
    defaults.update(overrides)
    await SqlAlchemyAdminSettingsRepository(db).save_security(AdminSecuritySettings(**defaults))
    await db.commit()


async def _login(client, username="system", password=PASSWORD):
    return await client.post(
        "/api/v1/auth/login/access-token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _decode(token: str) -> dict:
    return jwt.decode(
        token,
        cfg.security.secret_key_non_persistent,
        algorithms=[cfg.security.algorithm],
        options={"verify_exp": False},
    )


async def _enrol(client, setup_token: str):
    secret = (
        await client.post("/api/v1/web/users/me/totp/enroll", headers=_auth(setup_token))
    ).json()["secret"]
    return await client.post(
        "/api/v1/web/users/me/totp/confirm",
        json={"totp_code": pyotp.TOTP(secret).now()},
        headers=_auth(setup_token),
    )


async def _backdate_created_at(db, minutes: int, public_id: str | None = None) -> None:
    when = datetime.now(UTC) - timedelta(minutes=minutes)
    if public_id is None:
        await db.execute(text("UPDATE user_session_table SET created_at = :when"), {"when": when})
    else:
        # SQLite stores SQLAlchemy's Uuid() column as a dashless 32-char hex
        # string, unlike the dashed form the JWT's `sid` claim carries (see
        # test_api_session_timeout.py's own note on this).
        await db.execute(
            text("UPDATE user_session_table SET created_at = :when WHERE public_id = :pid"),
            {"when": when, "pid": public_id.replace("-", "")},
        )
    await db.commit()


@pytest.fixture
async def system_session(client, create_user, db) -> str:
    """A system user, enrolled in 2FA and holding one real session token,
    via the same forced-enrolment flow a first login would take."""
    await create_user(username="system", email="system@example.com", is_systemuser=True)
    await _set_security(db)
    setup_token = (await _login(client)).json()["setup_token"]
    return (await _enrol(client, setup_token)).json()["access_token"]


# ── Login forces enrolment, unconditionally ────────────────────────────


class TestLoginForcesEnrolment:
    async def test_forced_even_without_global_enforcement(self, client, create_user, db):
        await create_user(username="system", email="system@example.com", is_systemuser=True)
        await _set_security(db, enforce_totp=False)

        body = (await _login(client)).json()

        assert body.get("totp_setup_required") is True
        assert "access_token" not in body

    async def test_enrol_and_confirm_via_the_setup_token_yields_a_session(
        self, client, create_user, db
    ):
        await create_user(username="system", email="system@example.com", is_systemuser=True)
        await _set_security(db, enforce_totp=False)
        setup_token = (await _login(client)).json()["setup_token"]

        response = await _enrol(client, setup_token)

        assert response.status_code == 200
        assert response.json()["access_token"]

    async def test_the_new_session_works_on_an_ordinary_route(self, client, system_session):
        response = await client.get("/api/v1/web/users/me", headers=_auth(system_session))

        assert response.status_code == 200
        assert response.json()["username"] == "system"


# ── No "trust this device" ──────────────────────────────────────────────


class TestTrustedDeviceIsDisabled:
    async def test_challenge_reports_zero_days_even_when_the_setting_is_thirty(
        self, client, create_user, db
    ):
        system = await create_user(
            username="system", email="system@example.com", is_systemuser=True
        )
        system.totp_secret = generate_totp_secret()
        system.totp_enabled = True
        await SqlAlchemyUserRepository(db).save(system)
        await db.commit()
        await _set_security(db, totp_trusted_device_days=30)

        body = (await _login(client)).json()

        assert body["totp_required"] is True
        assert body["trusted_device_days"] == 0

    async def test_login_totp_with_trust_device_sets_no_cookie_and_creates_no_row(
        self, client, create_user, db
    ):
        system = await create_user(
            username="system", email="system@example.com", is_systemuser=True
        )
        secret = generate_totp_secret()
        system.totp_secret = secret
        system.totp_enabled = True
        await SqlAlchemyUserRepository(db).save(system)
        await db.commit()
        await _set_security(db, totp_trusted_device_days=30)
        partial_token = (await _login(client)).json()["partial_token"]

        response = await client.post(
            "/api/v1/auth/login/totp",
            json={
                "partial_token": partial_token,
                "totp_code": pyotp.TOTP(secret).now(),
                "trust_device": True,
            },
        )

        assert response.status_code == 200
        assert TRUSTED_DEVICE_COOKIE not in response.cookies
        count = (await db.execute(text("SELECT COUNT(*) FROM user_trusted_device_table"))).scalar()
        assert count == 0


# ── Session token exp claim ────────────────────────────────────────────


class TestSessionTokenExpClaim:
    def test_system_user_token_carries_exp_near_fifteen_minutes(self, system_session):
        payload = _decode(system_session)

        assert "exp" in payload
        remaining = payload["exp"] - datetime.now(UTC).timestamp()
        assert 14 * 60 <= remaining <= 15 * 60

    async def test_normal_user_token_carries_no_exp_claim(self, client, create_user, db):
        await create_user()
        await _set_security(db)

        token = (await _login(client, username="tester")).json()["access_token"]

        assert "exp" not in _decode(token)


# ── Hard session expiry (row-level) ────────────────────────────────────


class TestHardSessionExpiry:
    async def test_sixteen_minutes_backdated_is_expired(self, client, system_session, db):
        await _backdate_created_at(db, 16)

        response = await client.get("/api/v1/web/users/me", headers=_auth(system_session))

        assert response.status_code == 401
        assert response.json()["detail"] == "Session expired"

    async def test_fourteen_minutes_backdated_is_still_alive(self, client, system_session, db):
        await _backdate_created_at(db, 14)

        response = await client.get("/api/v1/web/users/me", headers=_auth(system_session))

        assert response.status_code == 200

    async def test_a_normal_user_is_unaffected_by_the_same_backdating(
        self, client, create_user, db
    ):
        await create_user()
        await _set_security(db)
        token = (await _login(client, username="tester")).json()["access_token"]

        await _backdate_created_at(db, 16)

        assert (await client.get("/api/v1/web/users/me", headers=_auth(token))).status_code == 200


# ── GET /users/me/sessions/current ──────────────────────────────────


class TestCurrentSessionEndpoint:
    async def test_system_user_gets_an_expiry_about_fifteen_minutes_out(
        self, client, system_session
    ):
        response = await client.get(
            "/api/v1/web/users/me/sessions/current", headers=_auth(system_session)
        )

        assert response.status_code == 200
        body = response.json()
        assert body["expires_at"] is not None
        assert body["server_time"] is not None

        expires_at = datetime.fromisoformat(body["expires_at"])
        server_time = datetime.fromisoformat(body["server_time"])
        assert (
            timedelta(minutes=14, seconds=50)
            <= expires_at - server_time
            <= timedelta(minutes=15, seconds=10)
        )

    async def test_normal_user_gets_the_absolute_lifetime(self, client, create_user, db):
        await create_user()
        await _set_security(db)
        token = (await _login(client, username="tester")).json()["access_token"]

        response = await client.get("/api/v1/web/users/me/sessions/current", headers=_auth(token))

        assert response.status_code == 200
        body = response.json()
        lifetime = datetime.fromisoformat(body["expires_at"]) - datetime.fromisoformat(
            body["server_time"]
        )
        assert timedelta(days=29, hours=23) < lifetime <= timedelta(days=30)


# ── Sessions list omits hard-expired rows ───────────────────────────────


class TestSessionsListOmitsHardExpired:
    async def test_a_hard_expired_session_is_dropped(self, client, system_session, db):
        system = await SqlAlchemyUserRepository(db).get_by_username("system")
        partial_token = (await _login(client)).json()["partial_token"]
        second_token = (
            await client.post(
                "/api/v1/auth/login/totp",
                json={
                    "partial_token": partial_token,
                    "totp_code": pyotp.TOTP(system.totp_secret).now(),
                },
            )
        ).json()["access_token"]

        first_sid = _decode(system_session)["sid"]
        await _backdate_created_at(db, 16, public_id=first_sid)

        response = await client.get("/api/v1/web/users/me/sessions/", headers=_auth(second_token))

        assert response.status_code == 200
        sids = {row["public_id"] for row in response.json()}
        assert first_sid not in sids
        assert len(response.json()) == 1


# ── Self-service 2FA disable is refused ─────────────────────────────


class TestSelfServiceTotpDisableIsRefused:
    async def test_refused_with_403_even_with_a_valid_code(self, client, create_user, db):
        system = await create_user(
            username="system", email="system@example.com", is_systemuser=True
        )
        secret = generate_totp_secret()
        system.totp_secret = secret
        system.totp_enabled = True
        await SqlAlchemyUserRepository(db).save(system)
        await db.commit()
        await _set_security(db)
        partial_token = (await _login(client)).json()["partial_token"]
        token = (
            await client.post(
                "/api/v1/auth/login/totp",
                json={"partial_token": partial_token, "totp_code": pyotp.TOTP(secret).now()},
            )
        ).json()["access_token"]

        # TestClient.delete() (this starlette/httpx pairing) has no `json`
        # kwarg, unlike .post()/.request(); route around it the same way.
        response = await client.request(
            "DELETE",
            "/api/v1/web/users/me/totp/",
            json={"totp_code": pyotp.TOTP(secret).now()},
            headers=_auth(token),
        )

        assert response.status_code == 403


# ── PATs ─────────────────────────────────────────────────────────────


class TestPersonalAccessTokens:
    async def test_create_is_refused_with_403(self, client, system_session):
        response = await client.post(
            "/api/v1/web/users/me/personal-access-tokens/",
            json={"name": "test", "permissions": [], "password": TEST_PASSWORD},
            headers=_auth(system_session),
        )

        assert response.status_code == 403

    async def test_a_pre_existing_token_is_refused_at_validation(self, client, create_user, db):
        """A system-account token that exists anyway (inserted directly,
        since creation is blocked outright) must not authenticate."""
        system = await create_user(
            username="system", email="system@example.com", is_systemuser=True
        )
        raw_token = "glados_pat_pre-existing-system-token"
        await SqlAlchemyPatRepository(db).save(
            PersonalAccessToken(
                id=0,
                name="legacy",
                token_hash=hash_pat(raw_token),
                token_prefix=display_prefix(raw_token),
                user_id=system.id,
                permissions=[],
                created=datetime.now(UTC),
                expires_at=None,
            )
        )
        await db.commit()

        response = await client.post(
            "/api/v1/auth/login/test-personal-access-token",
            headers={"X-Api-Key": raw_token},
        )

        assert response.status_code == 401


# ── A reset forces re-enrolment ───────────────────────────────────


class TestResetForcesReEnrolment:
    async def test_clearing_totp_fields_forces_setup_on_the_next_login(
        self, client, system_session, db
    ):
        system = await SqlAlchemyUserRepository(db).get_by_username("system")
        system.totp_secret = None
        system.totp_enabled = False
        await SqlAlchemyUserRepository(db).save(system)
        await db.commit()

        body = (await _login(client)).json()

        assert body.get("totp_setup_required") is True


# ── Single system user invariant, at the HTTP boundary ──────────────


class TestCreateUserCannotSetIsSystemuser:
    async def test_the_system_user_creating_one_gets_a_normal_user_back(
        self, client, system_session, db
    ):
        """UserCreateRequest does not declare is_systemuser at all, so
        pydantic silently drops it; the request succeeds (the system user
        holds write:settings implicitly) and simply creates a normal
        account, it never gets refused for asking."""
        # create_user's welcome mail is non-fatal to the use case, but the
        # SmtpMailService dependency itself is built eagerly and needs the
        # (otherwise-unseeded-here) mail settings row to exist at all.
        await SqlAlchemyAdminSettingsRepository(db).save_mail(
            AdminMailSettings(
                id=1,
                enabled=False,
                host="",
                port=587,
                user="",
                password=None,
                from_address=None,
                use_tls=True,
                use_ssl=False,
                verify_certificate=True,
                from_display_name="",
                reply_to=None,
                send_limit_per_hour=20,
                send_lock_minutes=60,
                alert_recipients=[],
            )
        )
        await db.commit()

        response = await client.post(
            "/api/v1/web/users/",
            json={
                "username": "newperson",
                "full_name": "New Person",
                "email": "newperson@example.com",
                "password": "a-strong-password",
                "is_systemuser": True,
            },
            headers=_auth(system_session),
        )

        assert response.status_code == 201
        assert response.json()["is_systemuser"] is False
