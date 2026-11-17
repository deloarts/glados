"""
The web session cookie: login sets an httponly, Secure,
SameSite=Strict cookie carrying the session token; the cookie alone
authenticates the web surface; a state-changing (unsafe-method) request
authenticated via the cookie is rejected without the app's CSRF header,
while the same request authenticated via a bearer Authorization header
is not (see auth_deps.py's module docstring for why); and logout clears
the cookie and revokes the session it names.

Clients here use an https base_url: the cookie is Secure outside debug
mode, and httpx's jar (correctly) refuses to send Secure cookies back
over plain http. Same pattern as test_api_trusted_devices.py.
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

from .conftest import auth_headers

PASSWORD = "test-password"
LOGIN_URL = "/api/v1/auth/login/access-token"
LOGOUT_URL = "/api/v1/auth/logout"
SESSIONS = "/api/v1/web/users/me/sessions/"
COOKIE = "glados_session"
CSRF_HEADER = {"X-Requested-With": "glados"}


@pytest.fixture
async def https_client():
    """Cookie-carrying client. https so the Secure cookie flows back."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("testclient", 50000)),
        base_url="https://testserver",
        follow_redirects=True,
    ) as c:
        yield c


@pytest.fixture
async def relaxed_security(db):
    """enforce_totp defaults to on for write:settings holders; these tests
    care about the cookie/CSRF path, not enrolment."""
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


async def _login(client, username="tester"):
    return await client.post(
        LOGIN_URL,
        data={"username": username, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


class TestLoginSetsTheCookie:
    async def test_login_sets_an_httponly_secure_strict_cookie(
        self, https_client, create_user, relaxed_security
    ):
        await create_user()

        response = await _login(https_client)

        assert response.status_code == 200
        assert COOKIE in https_client.cookies
        set_cookie = response.headers["set-cookie"]
        assert "HttpOnly" in set_cookie
        assert "Secure" in set_cookie
        assert "samesite=strict" in set_cookie.lower()
        assert "Path=/" in set_cookie

    async def test_the_response_body_still_carries_the_token(
        self, https_client, create_user, relaxed_security
    ):
        """The frontend does not read this field (it relies on the
        cookie), and the test suite's own auth_client/auth_headers
        fixtures mint bearer tokens directly rather than going through
        this endpoint, but the body still carries access_token for any
        client that reads it."""
        await create_user()

        response = await _login(https_client)

        assert response.json()["access_token"]
        assert response.json()["token_type"] == "bearer"

    async def test_the_cookie_alone_authenticates_a_protected_route(
        self, https_client, create_user, relaxed_security
    ):
        await create_user()
        await _login(https_client)

        me = await https_client.get("/api/v1/web/users/me")

        assert me.status_code == 200
        assert me.json()["username"] == "tester"

    async def test_totp_login_also_sets_the_cookie(self, https_client, create_user, db):
        user = await create_user()
        secret = generate_totp_secret()
        user.totp_secret = secret
        user.totp_enabled = True
        await SqlAlchemyUserRepository(db).save(user)
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
                totp_trusted_device_days=0,
                max_login_attempts=0,
                lockout_duration_minutes=15,
                token_max_lifetime_days=3650,
            )
        )
        await db.commit()
        challenge = (await _login(https_client)).json()

        response = await https_client.post(
            "/api/v1/auth/login/totp",
            json={
                "partial_token": challenge["partial_token"],
                "totp_code": pyotp.TOTP(secret).now(),
            },
        )

        assert response.status_code == 200
        assert COOKIE in https_client.cookies


class TestCsrfHeader:
    async def test_cookie_authenticated_unsafe_request_without_the_header_is_rejected(
        self, https_client, create_user, relaxed_security
    ):
        await create_user()
        await _login(https_client)

        response = await https_client.delete(SESSIONS)

        assert response.status_code == 403

    async def test_cookie_authenticated_unsafe_request_with_the_header_succeeds(
        self, https_client, create_user, relaxed_security
    ):
        await create_user()
        await _login(https_client)

        response = await https_client.delete(SESSIONS, headers=CSRF_HEADER)

        assert response.status_code == 200

    async def test_cookie_authenticated_safe_request_needs_no_header(
        self, https_client, create_user, relaxed_security
    ):
        await create_user()
        await _login(https_client)

        assert (await https_client.get("/api/v1/web/users/me")).status_code == 200

    async def test_bearer_authenticated_unsafe_request_needs_no_header(self, client, create_user):
        """A bearer token has to be known by the caller, a browser cannot
        attach one automatically, so it carries no CSRF risk of its own
        (see auth_deps.py's module docstring)."""
        user = await create_user()

        response = await client.delete(SESSIONS, headers=await auth_headers(user))

        assert response.status_code == 200


class TestLogout:
    async def test_logout_clears_the_cookie(self, https_client, create_user, relaxed_security):
        await create_user()
        await _login(https_client)

        response = await https_client.post(LOGOUT_URL, headers=CSRF_HEADER)

        assert response.status_code == 200
        assert COOKIE not in https_client.cookies

    async def test_logout_revokes_the_session_the_cookie_named(
        self, https_client, create_user, relaxed_security
    ):
        await create_user()
        await _login(https_client)
        old_cookie = https_client.cookies[COOKIE]

        await https_client.post(LOGOUT_URL, headers=CSRF_HEADER)

        # Replay the now-revoked cookie value explicitly. The client's own
        # jar already dropped it; this proves the session row is dead, not
        # just the local cookie.
        https_client.cookies.set(COOKIE, old_cookie)
        me = await https_client.get("/api/v1/web/users/me")
        assert me.status_code == 401

    async def test_logout_requires_the_csrf_header_too(
        self, https_client, create_user, relaxed_security
    ):
        await create_user()
        await _login(https_client)

        assert (await https_client.post(LOGOUT_URL)).status_code == 403

    async def test_logout_without_a_prior_login_is_a_harmless_no_op(self, https_client):
        response = await https_client.post(LOGOUT_URL, headers=CSRF_HEADER)

        assert response.status_code == 200


class TestRevokeCurrentSessionClearsTheCookie:
    async def test_revoking_ones_own_current_session_via_the_sessions_list_clears_the_cookie(
        self, https_client, create_user, relaxed_security
    ):
        await create_user()
        await _login(https_client)
        current = next(s for s in (await https_client.get(SESSIONS)).json() if s["is_current"])

        response = await https_client.delete(
            f"{SESSIONS}{current['public_id']}", headers=CSRF_HEADER
        )

        assert response.status_code == 200
        assert COOKIE not in https_client.cookies
