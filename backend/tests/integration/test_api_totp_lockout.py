"""
Two protections on the TOTP code-verification paths, both new:

  1. Throttle on POST /login/totp, unlike password lockout (opt-in via
     max_login_attempts, default off), this is always on: a 6-digit code's
     entire security margin is that guessing it is slow, and login_totp is
     reachable with nothing but a stolen password (see
     login_policy.py's TOTP-throttle section).
  2. Replay protection on every code-accepting path (login_totp,
     confirm_totp, disable_totp), a code that verifies is only accepted
     once, closing the window where an intercepted-but-not-yet-expired
     code could be reused.

The tracker is faked per test here (see fakes.py); the replay guard is
faked for every integration test by conftest.py's autouse `replay_guard`
fixture (real Redis state would otherwise persist across tests and cause
unrelated tests to collide, see that fixture's docstring), and requested
here by name where a test needs to assert on it. Both Redis
implementations are covered separately.
"""

import pyotp
import pytest
from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.platform.adapters.inbound.api.deps.services import get_login_attempt_tracker
from src.modules.platform.adapters.inbound.api.deps.services import get_replay_guard
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.services.login_policy import TOTP_LOCK_SECONDS
from src.modules.platform.domain.services.login_policy import TOTP_MAX_ATTEMPTS
from src.modules.platform.infrastructure.security.token import create_partial_token
from src.modules.platform.infrastructure.security.totp import generate_totp_secret
from tests.factories import TEST_PASSWORD
from tests.integration.fakes import FakeLoginAttemptTracker

PASSWORD = "test-password"


@pytest.fixture
def tracker():
    """Override the Redis-backed tracker for the duration of a test."""
    fake = FakeLoginAttemptTracker()
    app.dependency_overrides[get_login_attempt_tracker] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_login_attempt_tracker, None)


async def _seed_security(db) -> None:
    """A successful login_totp reads AdminSecuritySettings
    (assert_local_login_allowed), this integration DB never runs
    InitDatabase (see conftest.py's module docstring), so any test whose
    happy path reaches that line needs the row seeded first."""
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


@pytest.fixture
async def enrolled(create_user, db):
    """A user with 2FA already set up. Returns (user, secret) so a test can
    mint fresh codes with pyotp.TOTP(secret).now()."""
    await _seed_security(db)

    async def _make(username="tester", email="tester@example.com", **kw):
        user = await create_user(username=username, email=email, password=PASSWORD, **kw)
        secret = generate_totp_secret()
        user.totp_secret = secret
        user.totp_enabled = True
        saved = await SqlAlchemyUserRepository(db).save(user)
        await db.commit()
        return saved, secret

    return _make


async def _login_totp(client, partial_token: str, code: str):
    return await client.post(
        "/api/v1/auth/login/totp",
        json={"partial_token": partial_token, "totp_code": code},
    )


def _wrong_code(secret: str) -> str:
    real = pyotp.TOTP(secret).now()
    return "000000" if real != "000000" else "111111"


# ── Throttle ──────────────────────────────────────────────────────────


class TestThrottle:
    async def test_locks_after_the_configured_number_of_attempts(self, client, enrolled, tracker):
        user, secret = await enrolled()
        token = create_partial_token(user.id)

        for _ in range(TOTP_MAX_ATTEMPTS):
            await _login_totp(client, token, _wrong_code(secret))

        assert await tracker.is_locked(f"totp:{user.id}") is True

    async def test_does_not_lock_one_attempt_early(self, client, enrolled, tracker):
        user, secret = await enrolled()
        token = create_partial_token(user.id)

        for _ in range(TOTP_MAX_ATTEMPTS - 1):
            await _login_totp(client, token, _wrong_code(secret))

        assert await tracker.is_locked(f"totp:{user.id}") is False

    async def test_a_locked_challenge_gets_429(self, client, enrolled, tracker):
        user, secret = await enrolled()
        token = create_partial_token(user.id)
        for _ in range(TOTP_MAX_ATTEMPTS):
            await _login_totp(client, token, _wrong_code(secret))

        response = await _login_totp(client, token, _wrong_code(secret))

        assert response.status_code == 429

    async def test_the_correct_code_is_also_refused_while_locked(self, client, enrolled, tracker):
        """Otherwise the lock would only inconvenience typos, not an
        attacker who eventually guesses right, same rationale as
        test_api_login_lockout.py's password equivalent."""
        user, secret = await enrolled()
        token = create_partial_token(user.id)
        for _ in range(TOTP_MAX_ATTEMPTS):
            await _login_totp(client, token, _wrong_code(secret))

        response = await _login_totp(client, token, pyotp.TOTP(secret).now())

        assert response.status_code == 429

    async def test_the_response_says_how_long_to_wait(self, client, enrolled, tracker):
        user, secret = await enrolled()
        token = create_partial_token(user.id)
        for _ in range(TOTP_MAX_ATTEMPTS):
            await _login_totp(client, token, _wrong_code(secret))

        response = await _login_totp(client, token, _wrong_code(secret))

        assert response.headers["Retry-After"] == str(TOTP_LOCK_SECONDS)


# ── Unlocking ─────────────────────────────────────────────────────────


class TestUnlocking:
    async def test_a_successful_login_clears_earlier_failures(
        self, client, enrolled, tracker, replay_guard
    ):
        user, secret = await enrolled()
        token = create_partial_token(user.id)
        for _ in range(TOTP_MAX_ATTEMPTS - 1):
            await _login_totp(client, token, _wrong_code(secret))

        response = await _login_totp(client, token, pyotp.TOTP(secret).now())

        assert response.status_code == 200
        assert tracker.failures.get(f"totp:{user.id}") is None

    async def test_access_returns_when_the_lock_lapses(
        self, client, enrolled, tracker, replay_guard
    ):
        user, secret = await enrolled()
        token = create_partial_token(user.id)
        for _ in range(TOTP_MAX_ATTEMPTS):
            await _login_totp(client, token, _wrong_code(secret))
        assert (await _login_totp(client, token, _wrong_code(secret))).status_code == 429

        tracker.expire(f"totp:{user.id}")

        response = await _login_totp(client, token, pyotp.TOTP(secret).now())
        assert response.status_code == 200


# ── Fail-open ─────────────────────────────────────────────────────────


class TestFailsOpen:
    async def test_totp_login_still_works_when_the_tracker_is_broken(
        self, client, enrolled, replay_guard
    ):
        """A Redis outage must degrade the throttle, not TOTP login itself."""

        class BrokenTracker:
            async def record_failure(self, key: str) -> int:
                return 0

            async def reset(self, key: str) -> None:
                return None

            def lock(self, key: str, seconds: int) -> None:
                return None

            async def lock_ttl(self, key: str) -> int:
                return 0

            async def clear_all(self) -> int:
                return 0

        user, secret = await enrolled()
        token = create_partial_token(user.id)
        app.dependency_overrides[get_login_attempt_tracker] = BrokenTracker
        try:
            for _ in range(TOTP_MAX_ATTEMPTS + 2):
                assert (await _login_totp(client, token, _wrong_code(secret))).status_code == 401
            assert (await _login_totp(client, token, pyotp.TOTP(secret).now())).status_code == 200
        finally:
            app.dependency_overrides.pop(get_login_attempt_tracker, None)

    async def test_totp_login_still_works_when_the_replay_guard_is_broken(
        self, client, enrolled, tracker
    ):
        """A Redis outage must degrade replay protection, not TOTP login,
        the same code would be accepted twice while this persists, which is
        the accepted trade against blocking every login outright."""

        class BrokenReplayGuard:
            async def consume_once(self, key: str, ttl_seconds: int) -> bool:
                return True

        user, secret = await enrolled()
        token = create_partial_token(user.id)
        app.dependency_overrides[get_replay_guard] = BrokenReplayGuard
        try:
            code = pyotp.TOTP(secret).now()
            assert (await _login_totp(client, token, code)).status_code == 200
        finally:
            app.dependency_overrides.pop(get_replay_guard, None)


# ── Replay protection ────────────────────────────────────────────────


class TestReplayProtection:
    async def test_the_same_code_cannot_log_in_twice(self, client, enrolled, tracker, replay_guard):
        user, secret = await enrolled()
        token = create_partial_token(user.id)
        code = pyotp.TOTP(secret).now()

        first = await _login_totp(client, token, code)
        assert first.status_code == 200

        second = await _login_totp(client, token, code)
        assert second.status_code == 401
        assert second.json()["code"] == "InvalidTOTPCodeError"

    async def test_a_replayed_code_still_counts_toward_the_lockout(
        self, client, enrolled, tracker, replay_guard
    ):
        """A replay attempt is indistinguishable from a wrong code to the
        attacker probing it, it must burn the same budget."""
        user, secret = await enrolled()
        token = create_partial_token(user.id)
        code = pyotp.TOTP(secret).now()
        await _login_totp(client, token, code)  # succeeds and consumes the code (not a failure)

        for _ in range(TOTP_MAX_ATTEMPTS):
            await _login_totp(client, token, code)  # every one of these replays and fails

        assert await tracker.is_locked(f"totp:{user.id}") is True

    async def test_confirm_totp_rejects_a_replayed_code(
        self, auth_client, replay_guard, seeded_security
    ):
        """ConfirmTOTPEnrollment has no "already enabled" guard of its own
        (confirming twice with two different fresh codes is fine, it just
        re-saves totp_enabled=True), so submitting the exact same code
        twice succeeding a second time would mean nothing but this replay
        guard was ever stopping it."""
        client = await auth_client()
        enrolled = await client.post(
            "/api/v1/web/users/me/totp/enroll", json={"password": TEST_PASSWORD}
        )
        secret = enrolled.json()["secret"]
        code = pyotp.TOTP(secret).now()

        first = await client.post("/api/v1/web/users/me/totp/confirm", json={"totp_code": code})
        assert first.status_code == 200

        second = await client.post("/api/v1/web/users/me/totp/confirm", json={"totp_code": code})
        assert second.status_code != 200

    # disable_totp's replay path is the same _replay_protected_verify
    # wrapper as confirm_totp above, parameterized by flow="disable",
    # covered directly (not through HTTP) in
    # tests/unit/test_totp_security.py, because DisableTOTP itself clears
    # totp_secret on success, so a second sequential HTTP call fails with
    # TOTPNotEnabledError before ever reaching the replay-guarded verify(),
    # the state machine masks the very thing this would be testing.
