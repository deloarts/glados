"""
The security log's write side (application/services/security_audit.py):
the request's address and user agent fill in what a caller leaves out, free
text is bounded, the disabled recorder writes nothing, and the login
throttle reports each scope once, when it locks or starts delaying, so the
log gets one throttle entry rather than one per refused attempt.
"""

from typing import Any

from src.modules.platform.application.services.login_throttle import SCOPE_ACCOUNT
from src.modules.platform.application.services.login_throttle import SCOPE_ACCOUNT_ON_ADDRESS
from src.modules.platform.application.services.login_throttle import SCOPE_ADDRESS
from src.modules.platform.application.services.login_throttle import LoginThrottle
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.entities.security_event import USER_AGENT_MAX_LENGTH
from src.modules.platform.domain.entities.security_event import SecurityEvent
from src.modules.platform.domain.services.login_policy import IP_MAX_FAILED_LOGINS
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventOutcome
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.logging.context import client_ip_var
from src.modules.platform.infrastructure.logging.context import user_agent_var
from tests.factories import make_user
from tests.integration.fakes import FakeLoginAttemptTracker


class RecordingLog:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    async def append(self, event: SecurityEvent) -> None:
        self.events.append(event)


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
        "max_login_attempts": 2,
        "lockout_duration_minutes": 15,
        "token_max_lifetime_days": 3650,
    }
    fields.update(overrides)
    return AdminSecuritySettings(**fields)


class TestSecurityAudit:
    async def test_the_request_fills_in_address_and_user_agent(self) -> None:
        log = RecordingLog()
        actor = make_user(id=7, username="alice")
        ip_token = client_ip_var.set("10.0.0.7")
        agent_token = user_agent_var.set("x" * (USER_AGENT_MAX_LENGTH + 50))
        try:
            await SecurityAudit(log).record(
                SecurityEventType.PAT_CREATED, actor=actor, target_user=actor, target_id=3
            )
        finally:
            client_ip_var.reset(ip_token)
            user_agent_var.reset(agent_token)

        (event,) = log.events
        assert event.outcome == SecurityEventOutcome.SUCCESS
        assert (event.actor_user_id, event.actor_username) == (7, "alice")
        assert (event.target_user_id, event.target_id) == (7, 3)
        assert event.client_ip == "10.0.0.7"
        assert event.user_agent is not None and len(event.user_agent) == USER_AGENT_MAX_LENGTH

    async def test_a_caller_value_wins_over_the_request(self) -> None:
        log = RecordingLog()
        token = client_ip_var.set("10.0.0.7")
        try:
            await SecurityAudit(log).record(
                SecurityEventType.LOGIN, actor=None, client_ip="192.0.2.1"
            )
        finally:
            client_ip_var.reset(token)

        assert log.events[0].client_ip == "192.0.2.1"
        assert log.events[0].actor_username is None

    async def test_the_disabled_recorder_records_nothing(self) -> None:
        audit = SecurityAudit.disabled()

        await audit.record(SecurityEventType.LOGIN, actor=None)

        assert audit.records is False

    async def test_one_throttle_event_per_scope(self) -> None:
        log = RecordingLog()

        await SecurityAudit(log).record_throttled(None, [SCOPE_ADDRESS, SCOPE_ACCOUNT])

        assert [e.detail for e in log.events] == [{"scope": "address"}, {"scope": "account"}]
        assert {e.event_type for e in log.events} == {SecurityEventType.LOGIN_THROTTLED}


class TestThrottleReportsLocks:
    def setup_method(self) -> None:
        self.throttle = LoginThrottle(FakeLoginAttemptTracker())
        self.security = make_security()

    async def test_reaching_the_limit_reports_the_pair_and_the_account(self) -> None:
        first = await self.throttle.record_failure("alice", "10.0.0.7", self.security)
        second = await self.throttle.record_failure("alice", "10.0.0.7", self.security)

        assert first == []
        assert second == [SCOPE_ACCOUNT_ON_ADDRESS, SCOPE_ACCOUNT]

    async def test_a_growing_delay_is_reported_only_when_it_starts(self) -> None:
        for address in ("10.0.0.1", "10.0.0.2"):
            await self.throttle.record_failure("alice", address, self.security)

        third = await self.throttle.record_failure("alice", "10.0.0.3", self.security)

        assert SCOPE_ACCOUNT not in third

    async def test_an_address_lock_is_reported(self) -> None:
        reported: list[str] = []
        for n in range(IP_MAX_FAILED_LOGINS):
            reported += await self.throttle.record_failure(f"user{n}", "10.0.0.9", self.security)

        assert reported.count(SCOPE_ADDRESS) == 1
