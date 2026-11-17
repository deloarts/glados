"""
The login throttle's three scopes (application/services/login_throttle.py)
and the policy behind them (domain/services/login_policy.py): the address,
the username on one address, and the growing delay of the username alone.
"""

from typing import Any

import pytest

from src.modules.platform.application.services.login_throttle import LoginThrottle
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.exceptions import LoginLockedError
from src.modules.platform.domain.services.login_policy import IP_LOCK_SECONDS
from src.modules.platform.domain.services.login_policy import IP_MAX_FAILED_LOGINS
from src.modules.platform.domain.services.login_policy import USERNAME_DELAY_CAP_SECONDS
from src.modules.platform.domain.services.login_policy import username_delay_seconds
from tests.integration.fakes import FakeLoginAttemptTracker

IP = "10.0.0.7"


def make_security(**overrides: Any) -> AdminSecuritySettings:
    fields: dict[str, Any] = {
        "id": 1,
        "enforce_totp": False,
        "allow_rfid_login": True,
        "allow_local_login": True,
        "enable_api_key_auth": False,
        "min_password_length": 8,
        "session_timeout_minutes": 1440,
        "totp_trusted_device_days": 0,
        "max_login_attempts": 3,
        "lockout_duration_minutes": 15,
        "token_max_lifetime_days": 3650,
    }
    fields.update(overrides)
    return AdminSecuritySettings(**fields)


class TestUsernameDelay:
    def test_nothing_below_the_limit(self):
        assert username_delay_seconds(2, 3) == 0

    def test_doubles_from_one_second_at_the_limit(self):
        assert [username_delay_seconds(n, 3) for n in range(3, 7)] == [1, 2, 4, 8]

    def test_is_capped(self):
        assert username_delay_seconds(500, 3) == USERNAME_DELAY_CAP_SECONDS

    def test_zero_means_no_delay(self):
        assert username_delay_seconds(500, 0) == 0


class TestLoginThrottle:
    def setup_method(self):
        self.attempts = FakeLoginAttemptTracker()
        self.throttle = LoginThrottle(self.attempts)

    async def test_failures_count_on_every_scope_under_the_normalised_name(self):
        await self.throttle.record_failure(" Alice ", IP, make_security())

        assert self.attempts.failures["alice"] == 1
        assert self.attempts.failures[f"alice|{IP}"] == 1
        assert [k for k in self.attempts.failures if k.startswith(f"ip:{IP}@")]

    async def test_the_pair_locks_for_the_configured_duration(self):
        for _ in range(3):
            await self.throttle.record_failure("alice", IP, make_security())

        assert self.attempts.locks[f"alice|{IP}"] == 15 * 60
        with pytest.raises(LoginLockedError) as exc_info:
            await self.throttle.assert_allowed("alice", IP)
        assert exc_info.value.retry_after_seconds == 15 * 60

    async def test_another_address_only_waits_out_the_delay(self):
        for _ in range(3):
            await self.throttle.record_failure("alice", IP, make_security())

        with pytest.raises(LoginLockedError) as exc_info:
            await self.throttle.assert_allowed("alice", "10.9.9.9")
        assert exc_info.value.retry_after_seconds == 1

        self.attempts.expire("delay:alice")
        await self.throttle.assert_allowed("alice", "10.9.9.9")

    async def test_unlimited_attempts_lock_and_delay_nothing(self):
        for _ in range(10):
            await self.throttle.record_failure("alice", IP, make_security(max_login_attempts=0))

        await self.throttle.assert_allowed("alice", IP)
        assert self.attempts.locks == {}

    async def test_an_address_failing_on_many_names_is_locked(self):
        security = make_security(max_login_attempts=0)
        for n in range(IP_MAX_FAILED_LOGINS):
            await self.throttle.record_failure(f"guess{n}", IP, security)

        assert self.attempts.locks == {f"ip:{IP}": IP_LOCK_SECONDS}
        with pytest.raises(LoginLockedError):
            await self.throttle.assert_allowed("someone-else", IP)
        await self.throttle.assert_allowed("someone-else", "10.9.9.9")

    async def test_a_request_without_an_address_skips_the_address_scope(self):
        await self.throttle.record_failure("alice", None, make_security())

        assert set(self.attempts.failures) == {"alice", "alice|unknown"}

    async def test_success_clears_the_name_but_not_the_address(self):
        security = make_security()
        await self.throttle.record_failure("alice", IP, security)
        await self.throttle.record_failure("alice", IP, security)
        await self.throttle.record_failure("alice", IP, security)

        await self.throttle.record_success("ALICE", IP)

        assert "alice" not in self.attempts.failures
        assert set(self.attempts.locks) == set()
        assert [k for k in self.attempts.failures if k.startswith("ip:")]

    async def test_release_frees_the_name_on_every_address(self):
        await self.attempts.lock("alice|10.0.0.1", 900)
        await self.attempts.lock("alice|10.0.0.2", 900)
        await self.attempts.lock("delay:alice", 60)
        await self.attempts.lock("bob|10.0.0.1", 900)

        await self.throttle.release("Alice")

        assert self.attempts.locks == {"bob|10.0.0.1": 900}
