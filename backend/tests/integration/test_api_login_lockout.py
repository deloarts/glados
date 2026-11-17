"""
Failed-login lockout, driven by `max_login_attempts` /
`lockout_duration_minutes`.

Failed attempts are counted, so password guessing is throttled once the
limit is reached. The hard lock holds the username on the address that
failed (`PAIR`); the username alone only earns a growing delay (`DELAY`),
see application/services/login_throttle.py.

`max_login_attempts` of 0 means unlimited. A fresh install seeds 5 (the
shipped default, `TestShippedDefault` below pins it end-to-end), but an
*existing* install keeps whatever it already has, including 0, since no
migration touches a stored value. `TestDisabledByDefault` pins that 0
never locks anyone out, because a security feature silently starting to
lock people out on upgrade would be worse than the gap it closes.

The tracker is faked here (see fakes.py). Its Redis implementation is
covered separately in test_redis_login_attempt_tracker.py; keeping it out
of these tests is what lets the whole integration suite run with no Redis.
"""

import pytest
from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.init_db import InitDatabase
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.platform.adapters.inbound.api.deps.services import get_login_attempt_tracker
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from tests.integration.fakes import FakeLoginAttemptTracker

PASSWORD = "test-password"

# The address conftest's client sends from, and the throttle scopes of the
# user "tester" there.
CLIENT_ADDRESS = "testclient"
PAIR = f"tester|{CLIENT_ADDRESS}"
DELAY = "delay:tester"


@pytest.fixture
def tracker():
    """Override the Redis-backed tracker for the duration of a test."""
    fake = FakeLoginAttemptTracker()
    app.dependency_overrides[get_login_attempt_tracker] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_login_attempt_tracker, None)


async def _set_lockout(db, *, max_attempts: int, duration_minutes: int = 15) -> None:
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
            max_login_attempts=max_attempts,
            lockout_duration_minutes=duration_minutes,
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


# ── Off by default ────────────────────────────────────────────────────


class TestDisabledByDefault:
    async def test_zero_means_unlimited(self, client, create_user, db, tracker):
        await create_user()
        await _set_lockout(db, max_attempts=0)

        for _ in range(10):
            assert (await _login(client, password="wrong")).status_code == 401

        assert await tracker.is_locked(PAIR) is False
        assert await tracker.is_locked(DELAY) is False
        assert (await _login(client)).status_code == 200


# ── The shipped default ─────────────────────────────────────────────────


class TestShippedDefault:
    async def test_the_shipped_default_locks_after_five(self, client, create_user, db, tracker):
        """Pins the *shipped* default end-to-end, not just the DTO: seeds
        the security row through the real InitDatabase seeding path
        (skipping .run()'s Postgres-only advisory lock and the other
        domains this test does not need) instead of this file's own
        `_set_lockout` helper, so a regression in the seed literal itself
        would be caught here even if every use-case-level default test
        still passed."""
        await create_user()
        await InitDatabase(
            user_repo=None,  # type: ignore[arg-type]
            admin_settings_repo=SqlAlchemyAdminSettingsRepository(db),
            print_template_repo=None,  # type: ignore[arg-type]
            db=db,
        )._ensure_admin_settings()

        for _ in range(4):
            assert (await _login(client, password="wrong")).status_code == 401
        assert await tracker.is_locked(PAIR) is False

        await _login(client, password="wrong")  # 5th failure, reaches the limit
        assert await tracker.is_locked(PAIR) is True

        assert (await _login(client)).status_code == 429


# ── Locking ───────────────────────────────────────────────────────────


class TestLockout:
    async def test_locks_after_the_configured_number_of_failures(
        self, client, create_user, db, tracker
    ):
        await create_user()
        await _set_lockout(db, max_attempts=3)

        for _ in range(3):
            await _login(client, password="wrong")

        assert await tracker.is_locked(PAIR) is True

    async def test_does_not_lock_one_attempt_early(self, client, create_user, db, tracker):
        await create_user()
        await _set_lockout(db, max_attempts=3)

        for _ in range(2):
            await _login(client, password="wrong")

        assert await tracker.is_locked(PAIR) is False

    async def test_a_locked_account_gets_429(self, client, create_user, db, tracker):
        await create_user()
        await _set_lockout(db, max_attempts=1)
        await _login(client, password="wrong")

        response = await _login(client, password="wrong")

        assert response.status_code == 429

    async def test_the_correct_password_is_also_refused_while_locked(
        self, client, create_user, db, tracker
    ):
        """Otherwise the lock would only inconvenience the legitimate
        owner's typos, not an attacker who eventually guesses right."""
        await create_user()
        await _set_lockout(db, max_attempts=1)
        await _login(client, password="wrong")

        assert (await _login(client)).status_code == 429

    async def test_the_response_says_how_long_to_wait(self, client, create_user, db, tracker):
        await create_user()
        await _set_lockout(db, max_attempts=1, duration_minutes=15)
        await _login(client, password="wrong")

        response = await _login(client)

        assert response.headers["Retry-After"] == str(15 * 60)

    async def test_a_zero_minute_duration_still_locks(self, client, create_user, db, tracker):
        """A 0 there would otherwise clear the counter and lock for no time
        at all, worse than not locking, since it resets progress."""
        await create_user()
        await _set_lockout(db, max_attempts=1, duration_minutes=0)
        await _login(client, password="wrong")

        assert (await _login(client)).status_code == 429


# ── Scopes ────────────────────────────────────────────────────────────


async def _login_from(address: str, username="tester", password=PASSWORD):
    """A login from another client address than conftest's client."""
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=(address, 50000)),
        base_url="http://testserver",
    ) as other:
        return await _login(other, username=username, password=password)


class TestScopes:
    async def test_a_lock_holds_only_the_address_that_failed(
        self, client, create_user, db, tracker
    ):
        """The point of keying the hard lock on username and address: a
        stranger failing on purpose cannot shut the owner out everywhere."""
        await create_user()
        await _set_lockout(db, max_attempts=3)
        for _ in range(3):
            await _login(client, password="wrong")
        # The name alone only waits out its short delay.
        assert tracker.locks[DELAY] == 1
        tracker.expire(DELAY)

        assert (await _login(client)).status_code == 429
        assert (await _login_from("10.1.2.3")).status_code == 200

    async def test_the_delay_grows_with_failures_from_any_address(
        self, client, create_user, db, tracker
    ):
        await create_user()
        await _set_lockout(db, max_attempts=2)
        for address in ("10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4"):
            tracker.expire(DELAY)
            await _login_from(address, password="wrong")

        assert tracker.locks[DELAY] == 4  # 1, 2, then 4 seconds
        assert (await _login_from("10.0.0.5")).status_code == 429

    async def test_an_address_is_locked_after_failing_on_many_names(
        self, client, create_user, db, tracker
    ):
        from src.modules.platform.domain.services.login_policy import IP_LOCK_SECONDS
        from src.modules.platform.domain.services.login_policy import IP_MAX_FAILED_LOGINS

        await create_user()
        await _set_lockout(db, max_attempts=0)
        for n in range(IP_MAX_FAILED_LOGINS):
            await _login_from("10.9.9.9", username=f"guess{n}", password="x")

        assert tracker.locks["ip:10.9.9.9"] == IP_LOCK_SECONDS
        assert (await _login_from("10.9.9.9")).status_code == 429
        assert (await _login(client)).status_code == 200


# ── Unlocking ─────────────────────────────────────────────────────────


class TestUnlocking:
    async def test_a_successful_login_clears_earlier_failures(
        self, client, create_user, db, tracker
    ):
        await create_user()
        await _set_lockout(db, max_attempts=3)
        await _login(client, password="wrong")
        await _login(client, password="wrong")

        assert (await _login(client)).status_code == 200
        assert tracker.failures.get("tester") is None

    async def test_access_returns_when_the_lock_lapses(self, client, create_user, db, tracker):
        await create_user()
        await _set_lockout(db, max_attempts=1)
        await _login(client, password="wrong")
        assert (await _login(client)).status_code == 429

        tracker.expire(PAIR)
        tracker.expire(DELAY)

        assert (await _login(client)).status_code == 200


# ── Enumeration ───────────────────────────────────────────────────────


class TestUnknownUsernames:
    async def test_failures_are_counted_for_names_that_do_not_exist(
        self, client, create_user, db, tracker
    ):
        """Skipping them would make an unknown username cheaper than a
        wrong password, which is an enumeration oracle."""
        await create_user()
        await _set_lockout(db, max_attempts=2)

        await _login(client, username="ghost", password="x")
        await _login(client, username="ghost", password="x")

        assert await tracker.is_locked(f"ghost|{CLIENT_ADDRESS}") is True

    async def test_an_unknown_name_still_answers_401_not_404(
        self, client, create_user, db, tracker
    ):
        await create_user()
        await _set_lockout(db, max_attempts=5)

        assert (await _login(client, username="ghost", password="x")).status_code == 401


# ── Fail-open ─────────────────────────────────────────────────────────


class TestFailsOpen:
    async def test_login_still_works_when_the_tracker_is_broken(self, client, create_user, db):
        """A Redis outage must degrade lockout, not authentication. Failing
        closed would turn a cache blip into a total auth outage."""

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

        await create_user()
        await _set_lockout(db, max_attempts=1)
        app.dependency_overrides[get_login_attempt_tracker] = BrokenTracker
        try:
            assert (await _login(client, password="wrong")).status_code == 401
            assert (await _login(client)).status_code == 200
        finally:
            app.dependency_overrides.pop(get_login_attempt_tracker, None)


# ── CLI ───────────────────────────────────────────────────────────────


class TestUnlockUsersCli:
    async def test_clears_a_single_user(self, tracker):
        await tracker.lock("alice", 900)
        await tracker.lock("bob", 900)

        from src.bootstrap.cli.admin import unlock_users

        class _Args:
            username = "alice"

        with_patched = _patch_tracker(tracker)
        with with_patched:
            assert await unlock_users(_Args()) == 0  # type: ignore[arg-type]

        assert await tracker.is_locked("alice") is False
        assert await tracker.is_locked("bob") is True

    async def test_a_single_user_is_released_on_every_address(self, tracker):
        await tracker.lock("alice|10.0.0.1", 900)
        await tracker.lock("alice|10.0.0.2", 900)
        await tracker.lock("delay:alice", 60)
        await tracker.lock("bob|10.0.0.1", 900)

        from src.bootstrap.cli.admin import unlock_users

        class _Args:
            username = "Alice"

        with _patch_tracker(tracker):
            assert await unlock_users(_Args()) == 0  # type: ignore[arg-type]

        assert tracker.locks == {"bob|10.0.0.1": 900}

    async def test_clears_everyone(self, tracker):
        await tracker.lock("alice", 900)
        await tracker.lock("bob", 900)

        from src.bootstrap.cli.admin import unlock_users

        class _Args:
            username = None

        with _patch_tracker(tracker):
            assert await unlock_users(_Args()) == 0  # type: ignore[arg-type]

        assert await tracker.is_locked("alice") is False
        assert await tracker.is_locked("bob") is False


def _patch_tracker(fake):
    """unlock_users builds its own Redis tracker; swap the class it looks
    up so the command's logic can be exercised without Redis."""
    import contextlib

    import src.modules.platform.adapters.outbound.external.login_attempts.redis_login_attempt_tracker as module

    @contextlib.contextmanager
    def _ctx():
        original = module.RedisLoginAttemptTracker
        module.RedisLoginAttemptTracker = lambda _client: fake  # type: ignore[assignment,misc]
        try:
            yield
        finally:
            module.RedisLoginAttemptTracker = original  # type: ignore[misc]

    return _ctx()
