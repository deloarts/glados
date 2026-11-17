"""
The exact wire answer of every outcome of the two login routes: status,
body, Retry-After, cookies and their attributes, and which warnings the
request logs. The other login suites check behaviour; this one pins the
contract the frontend and the add-in see, including the refusals the
routes answer without an error code (lockout, and the inactive and
no-2FA refusals of the TOTP step).
"""

from typing import Any

import httpx
import pyotp
import pytest

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.trusted_device_repository import (
    SqlAlchemyTrustedDeviceRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.domain.entities.admin_settings.maintenance import AdminMaintenanceSettings
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.entities.trusted_device import make_trusted_device
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.security.token import create_partial_token
from src.modules.platform.infrastructure.security.totp import generate_totp_secret
from src.modules.platform.infrastructure.security.trusted_device import hash_trusted_device

PASSWORD = "test-password"
LOGIN = "/api/v1/auth/login/access-token"
TOTP = "/api/v1/auth/login/totp"

LOCKED_BODY = {"detail": "Too many failed attempts. Try again later."}
WRONG_PASSWORD_BODY = {"detail": "Incorrect username or password"}

_SECURE = {"secure"} if not cfg.debug else set()
SESSION_COOKIE_ATTRS = {
    "httponly",
    # The seeded absolute session lifetime of 30 days.
    f"max-age={30 * 24 * 60 * 60}",
    "path=/",
    "samesite=strict",
} | _SECURE
TRUSTED_COOKIE_ATTRS = {
    "httponly",
    f"max-age={30 * 86400}",
    "path=/api/v1/auth",
    "samesite=lax",
} | _SECURE


def _cookies(response: httpx.Response) -> list[tuple[str, set[str]]]:
    """Each Set-Cookie header as (name, lower-cased attributes), in order."""
    out = []
    for raw in response.headers.get_list("set-cookie"):
        name_value, *attrs = (part.strip() for part in raw.split(";"))
        out.append((name_value.partition("=")[0], {a.lower() for a in attrs}))
    return out


def _warnings(glados_caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in glados_caplog.records if r.levelname == "WARNING"]


async def _seed_security(db, **overrides: Any) -> None:
    fields: dict[str, Any] = {
        "id": 1,
        "enforce_totp": False,
        "allow_rfid_login": True,
        "allow_local_login": True,
        "enable_api_key_auth": False,
        "min_password_length": 8,
        "session_timeout_minutes": 0,
        "totp_trusted_device_days": 30,
        "max_login_attempts": 0,
        "lockout_duration_minutes": 15,
        "token_max_lifetime_days": 3650,
    }
    fields.update(overrides)
    await SqlAlchemyAdminSettingsRepository(db).save_security(AdminSecuritySettings(**fields))
    await db.commit()


async def _maintenance_on(db) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_maintenance(
        AdminMaintenanceSettings(id=1, enabled=True, message="Down for upgrades.")
    )
    await db.commit()


async def _enrol(db, user: User) -> str:
    secret = generate_totp_secret()
    user.totp_secret = secret
    user.totp_enabled = True
    await SqlAlchemyUserRepository(db).save(user)
    await db.commit()
    return secret


async def _login(
    client, username: str = "tester", password: str = PASSWORD, *, cookie: str | None = None
):
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if cookie is not None:
        headers["Cookie"] = cookie
    return await client.post(
        LOGIN, data={"username": username, "password": password}, headers=headers
    )


async def _totp(client, partial_token: str, code: str, *, trust: bool = False):
    return await client.post(
        TOTP, json={"partial_token": partial_token, "totp_code": code, "trust_device": trust}
    )


class TestPasswordStep:
    async def test_lockout(self, client, create_user, db, login_attempts, glados_caplog):
        await _seed_security(db)
        await create_user()
        login_attempts.locks["tester|testclient"] = 600

        response = await _login(client, "Tester")

        assert response.status_code == 429
        assert response.json() == LOCKED_BODY
        assert response.headers["Retry-After"] == "600"
        assert _cookies(response) == []
        assert _warnings(glados_caplog) == []

    async def test_wrong_password(self, client, create_user, db, login_attempts, glados_caplog):
        await _seed_security(db)
        await create_user()

        response = await _login(client, password="wrong")

        assert response.status_code == 401
        assert response.json() == WRONG_PASSWORD_BODY
        assert "Retry-After" not in response.headers
        assert _cookies(response) == []
        assert _warnings(glados_caplog) == [
            "Failed password login attempt for identifier 'tester'."
        ]
        assert login_attempts.failures["tester"] == 1
        assert login_attempts.failures["tester|testclient"] == 1

    async def test_unknown_name(self, client, create_user, db, login_attempts, glados_caplog):
        await _seed_security(db)
        await create_user()

        response = await _login(client, "Nobody", "wrong")

        assert response.status_code == 401
        assert response.json() == WRONG_PASSWORD_BODY
        assert _warnings(glados_caplog) == [
            "Failed password login attempt for identifier 'Nobody'."
        ]
        assert login_attempts.failures["nobody"] == 1

    async def test_inactive_account(self, client, create_user, db, glados_caplog):
        await _seed_security(db)
        await create_user(is_active=False)

        response = await _login(client)

        assert response.status_code == 403
        assert response.json() == {"detail": "Account is inactive.", "code": "InactiveUserError"}
        assert _cookies(response) == []
        assert _warnings(glados_caplog)[-1] == "InactiveUserError: Account is inactive."

    async def test_local_login_disabled(self, client, create_user, db, glados_caplog):
        await _seed_security(db, allow_local_login=False)
        await create_user()

        response = await _login(client)

        assert response.status_code == 403
        assert response.json() == {
            "detail": "Password login is currently disabled.",
            "code": "LocalLoginDisabledError",
        }
        assert _warnings(glados_caplog) == [
            "LocalLoginDisabledError: Password login is currently disabled."
        ]

    async def test_maintenance(self, client, create_user, db, glados_caplog):
        await _seed_security(db)
        await _maintenance_on(db)
        await create_user()

        response = await _login(client)

        assert response.status_code == 503
        assert response.json() == {"detail": "Down for upgrades.", "code": "MaintenanceModeError"}
        assert _warnings(glados_caplog) == ["MaintenanceModeError: Down for upgrades."]

    async def test_session(self, client, create_user, db, glados_caplog):
        await _seed_security(db)
        await create_user()

        response = await _login(client)

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"access_token", "token_type"}
        assert body["token_type"] == "bearer"
        assert _cookies(response) == [("glados_session", SESSION_COOKIE_ATTRS)]
        assert response.cookies["glados_session"] == body["access_token"]
        assert _warnings(glados_caplog) == []

    async def test_totp_challenge(self, client, create_user, db):
        await _seed_security(db)
        await _enrol(db, await create_user())

        response = await _login(client)

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"totp_required", "partial_token", "trusted_device_days"}
        assert (body["totp_required"], body["trusted_device_days"]) == (True, 30)
        assert _cookies(response) == []

    async def test_totp_setup_required(self, client, create_user, db):
        await _seed_security(db, enforce_totp=True)
        await create_user()

        response = await _login(client)

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"totp_setup_required", "setup_token", "username"}
        assert (body["totp_setup_required"], body["username"]) == (True, "tester")
        assert _cookies(response) == []

    async def test_trusted_device_skips_the_challenge(self, client, create_user, db):
        await _seed_security(db)
        user = await create_user()
        await _enrol(db, user)
        await SqlAlchemyTrustedDeviceRepository(db).save(
            make_trusted_device(
                user_id=user.id,
                token_hash=hash_trusted_device("device-secret"),
                trust_days=30,
                user_agent=None,
            )
        )
        await db.commit()

        response = await _login(client, cookie="glados_trusted_device=device-secret")

        assert response.status_code == 200
        assert set(response.json()) == {"access_token", "token_type"}
        assert _cookies(response) == [("glados_session", SESSION_COOKIE_ATTRS)]


class TestTotpStep:
    async def test_garbage_token(self, client, glados_caplog):
        response = await _totp(client, "garbage", "123456")

        assert response.status_code == 401
        assert response.json() == {
            "detail": "Invalid or expired TOTP challenge token",
            "code": "TOTPChallengeInvalidError",
        }
        assert _warnings(glados_caplog) == [
            "TOTPChallengeInvalidError: Invalid or expired TOTP challenge token"
        ]

    async def test_deleted_user(self, client):
        response = await _totp(client, create_partial_token(9999), "123456")

        assert response.status_code == 401
        assert response.json() == {"detail": "User not found", "code": "TOTPChallengeInvalidError"}

    async def test_lockout(self, client, create_user, db, login_attempts, glados_caplog):
        user = await create_user()
        secret = await _enrol(db, user)
        login_attempts.locks[f"totp:{user.id}"] = 300

        response = await _totp(client, create_partial_token(user.id), pyotp.TOTP(secret).now())

        assert response.status_code == 429
        assert response.json() == LOCKED_BODY
        assert response.headers["Retry-After"] == "300"
        assert _warnings(glados_caplog) == []

    async def test_inactive_account(self, client, create_user, db, glados_caplog):
        user = await create_user(is_active=False)
        secret = await _enrol(db, user)

        response = await _totp(client, create_partial_token(user.id), pyotp.TOTP(secret).now())

        assert response.status_code == 403
        assert response.json() == {"detail": "Account is inactive"}
        assert _warnings(glados_caplog) == []

    async def test_2fa_not_enabled(self, client, create_user, glados_caplog):
        user = await create_user()

        response = await _totp(client, create_partial_token(user.id), "123456")

        assert response.status_code == 400
        assert response.json() == {"detail": "2FA is not enabled for this account"}
        assert _warnings(glados_caplog) == []

    async def test_wrong_code(self, client, create_user, db, login_attempts, glados_caplog):
        user = await create_user()
        await _enrol(db, user)

        response = await _totp(client, create_partial_token(user.id), "000000x")

        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid TOTP code", "code": "InvalidTOTPCodeError"}
        assert _warnings(glados_caplog) == ["InvalidTOTPCodeError: Invalid TOTP code"]
        assert login_attempts.failures == {f"totp:{user.id}": 1}

    async def test_local_login_disabled(self, client, create_user, db):
        await _seed_security(db, allow_local_login=False)
        user = await create_user()
        secret = await _enrol(db, user)

        response = await _totp(client, create_partial_token(user.id), pyotp.TOTP(secret).now())

        assert response.status_code == 403
        assert response.json()["code"] == "LocalLoginDisabledError"

    async def test_maintenance(self, client, create_user, db):
        await _seed_security(db)
        await _maintenance_on(db)
        user = await create_user()
        secret = await _enrol(db, user)

        response = await _totp(client, create_partial_token(user.id), pyotp.TOTP(secret).now())

        assert response.status_code == 503
        assert response.json() == {"detail": "Down for upgrades.", "code": "MaintenanceModeError"}

    async def test_session_without_trust(self, client, create_user, db, glados_caplog):
        await _seed_security(db)
        user = await create_user()
        secret = await _enrol(db, user)

        response = await _totp(client, create_partial_token(user.id), pyotp.TOTP(secret).now())

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"access_token", "token_type"}
        assert body["token_type"] == "bearer"
        assert _cookies(response) == [("glados_session", SESSION_COOKIE_ATTRS)]
        assert _warnings(glados_caplog) == []

    async def test_session_with_trust(self, client, create_user, db):
        await _seed_security(db)
        user = await create_user()
        secret = await _enrol(db, user)

        response = await _totp(
            client, create_partial_token(user.id), pyotp.TOTP(secret).now(), trust=True
        )

        assert response.status_code == 200
        assert _cookies(response) == [
            ("glados_trusted_device", TRUSTED_COOKIE_ATTRS),
            ("glados_session", SESSION_COOKIE_ATTRS),
        ]
        assert response.cookies["glados_session"] == response.json()["access_token"]
