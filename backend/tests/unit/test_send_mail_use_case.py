"""
Unit tests for SendMail: the send:mail permission gate and the per-user
send-rate limit (mail_policy.py), admin-configurable via
AdminMailSettings.send_limit_per_hour/send_lock_minutes rather than fixed
module constants. No
database, no SMTP, no Redis, the rate tracker is an in-memory fake
mirroring tests/integration/fakes.FakeLoginAttemptTracker.
"""

from typing import Any

import pytest

from src.modules.platform.application.use_cases.mail.send_mail import SendMail
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import MailRateLimitedError
from src.modules.platform.domain.value_objects.permission import Permission
from tests import factories

# Matches AdminMailSettings' shipped default (see the migration and
# init_db's seed), what FakeAdminSettingsRepository below uses unless a
# test configures something else.
SEND_LIMIT_PER_HOUR = 20
SEND_LOCK_MINUTES = 60

# ── Helpers ───────────────────────────────────────────────────────────


def make_user(*, permissions: list[str] | None = None, **overrides: Any) -> User:
    """A user who may send mail unless the test passes other permissions."""
    if permissions is None:
        permissions = [Permission.SEND_MAIL]
    return factories.make_user(permissions=permissions, **overrides)


class FakeMailService:
    def __init__(self) -> None:
        self.sent: list[dict[str, str | None]] = []

    async def send_welcome(
        self, email, full_name, username, created_by_name, created_by_email, language=None
    ) -> None:
        raise NotImplementedError

    async def send_notification_digest(self, to, full_name, items, language=None) -> None:
        raise NotImplementedError

    async def send_schedule_error(self, task_name, message) -> None:
        raise NotImplementedError

    async def send_disc_space_warning(self, used_gb, total_gb) -> None:
        raise NotImplementedError

    async def send_custom(
        self,
        to: str,
        subject: str,
        html_body: str,
        cc: str | None = None,
        reply_to: str | None = None,
    ) -> None:
        self.sent.append(
            {"to": to, "subject": subject, "html_body": html_body, "cc": cc, "reply_to": reply_to}
        )

    async def send_test_mail(self, to: str) -> None:
        raise NotImplementedError


class FakeAdminSettingsRepository:
    """Minimal IAdminSettingsRepository stand-in: SendMail._assert_within_
    rate_limit only ever calls get_mail(), and only reads
    send_limit_per_hour/send_lock_minutes off the result."""

    def __init__(
        self,
        send_limit_per_hour: int = SEND_LIMIT_PER_HOUR,
        send_lock_minutes: int = SEND_LOCK_MINUTES,
    ) -> None:
        self._mail = AdminMailSettings(
            id=1,
            enabled=True,
            host="smtp.example.com",
            port=587,
            user="noreply",
            password=None,
            from_address="noreply@example.com",
            use_tls=True,
            use_ssl=False,
            verify_certificate=True,
            from_display_name="",
            reply_to=None,
            send_limit_per_hour=send_limit_per_hour,
            send_lock_minutes=send_lock_minutes,
            alert_recipients=[],
        )

    async def get_mail(self) -> AdminMailSettings:
        return self._mail


class FakeRateTracker:
    """In-memory ILoginAttemptTracker, see the port's docstring for why
    the mail rate limit reuses this shape. `broken` simulates a Redis
    outage: every method fails open, exactly like the real
    RedisLoginAttemptTracker."""

    def __init__(self, broken: bool = False) -> None:
        self._broken = broken
        self.failures: dict[str, int] = {}
        self.locks: dict[str, int] = {}

    async def record_failure(self, key: str) -> int:
        if self._broken:
            return 0
        self.failures[key] = self.failures.get(key, 0) + 1
        return self.failures[key]

    async def reset(self, key: str) -> None:
        self.failures.pop(key, None)
        self.locks.pop(key, None)

    async def lock(self, key: str, seconds: int) -> None:
        if self._broken:
            return
        self.locks[key] = seconds

    async def lock_ttl(self, key: str) -> int:
        if self._broken:
            return 0
        return self.locks.get(key, 0)

    async def clear_all(self) -> int:
        removed = len(self.failures) + len(self.locks)
        self.failures.clear()
        self.locks.clear()
        return removed


# ── Permission gate ──────────────────────────────────────────────────


class TestSendMailPermission:
    def setup_method(self):
        self.mail_service = FakeMailService()
        self.tracker = FakeRateTracker()
        self.settings = FakeAdminSettingsRepository()
        self.use_case = SendMail(
            mail_service=self.mail_service, rate_tracker=self.tracker, settings_repo=self.settings
        )

    async def test_actor_without_permission_is_rejected(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(
                actor, to="x@example.com", subject="Hi", html_body="<p>hi</p>"
            )
        assert self.mail_service.sent == []

    async def test_actor_with_permission_succeeds(self):
        actor = make_user(permissions=[Permission.SEND_MAIL])
        await self.use_case.execute(actor, to="x@example.com", subject="Hi", html_body="<p>hi</p>")
        assert len(self.mail_service.sent) == 1
        assert self.mail_service.sent[0]["to"] == "x@example.com"

    async def test_systemuser_bypasses_the_check(self):
        actor = make_user(permissions=[], is_systemuser=True)
        await self.use_case.execute(actor, to="x@example.com", subject="Hi", html_body="<p>hi</p>")
        assert len(self.mail_service.sent) == 1


# ── Rate limit ────────────────────────────────────────────────────────


class TestSendMailRateLimit:
    def setup_method(self):
        self.mail_service = FakeMailService()
        self.tracker = FakeRateTracker()
        self.settings = FakeAdminSettingsRepository()
        self.use_case = SendMail(
            mail_service=self.mail_service, rate_tracker=self.tracker, settings_repo=self.settings
        )
        self.actor = make_user(id=42)

    async def _send(self, use_case=None):
        await (use_case or self.use_case).execute(
            self.actor, to="x@example.com", subject="Hi", html_body="<p>hi</p>"
        )

    async def test_sends_up_to_the_limit_all_succeed(self):
        for _ in range(SEND_LIMIT_PER_HOUR):
            await self._send()
        assert len(self.mail_service.sent) == SEND_LIMIT_PER_HOUR

    async def test_the_send_that_crosses_the_limit_is_itself_rejected(self):
        for _ in range(SEND_LIMIT_PER_HOUR):
            await self._send()
        with pytest.raises(MailRateLimitedError):
            await self._send()
        # Rejected, not sent, the count stops at the limit.
        assert len(self.mail_service.sent) == SEND_LIMIT_PER_HOUR

    async def test_further_sends_stay_rejected_once_locked(self):
        for _ in range(SEND_LIMIT_PER_HOUR):
            await self._send()
        with pytest.raises(MailRateLimitedError):
            await self._send()

        # The lock (not a re-incremented counter) is what rejects this one,
        # see the pre-check in SendMail._assert_within_rate_limit.
        with pytest.raises(MailRateLimitedError):
            await self._send()
        assert len(self.mail_service.sent) == SEND_LIMIT_PER_HOUR

    async def test_rate_limit_is_scoped_per_user(self):
        other = make_user(id=99)
        for _ in range(SEND_LIMIT_PER_HOUR):
            await self._send()
        with pytest.raises(MailRateLimitedError):
            await self._send()

        # A different user's own quota is untouched.
        await self.use_case.execute(other, to="y@example.com", subject="Hi", html_body="<p>hi</p>")
        assert len(self.mail_service.sent) == SEND_LIMIT_PER_HOUR + 1

    async def test_redis_outage_fails_open(self):
        """A broken tracker must degrade the rate limit, not mail sending,
        same fail-open posture as login lockout."""
        broken_tracker = FakeRateTracker(broken=True)
        use_case = SendMail(
            mail_service=self.mail_service, rate_tracker=broken_tracker, settings_repo=self.settings
        )
        for _ in range(SEND_LIMIT_PER_HOUR + 5):
            await use_case.execute(
                self.actor, to="x@example.com", subject="Hi", html_body="<p>hi</p>"
            )
        assert len(self.mail_service.sent) == SEND_LIMIT_PER_HOUR + 5

    async def test_the_configured_limit_actually_gates_sends_not_a_hardcoded_one(self):
        """Proves the limit comes from AdminMailSettings.send_limit_per_hour,
        not a module constant: a tenant configured with a much lower limit
        is gated right after its third send."""
        low_limit_settings = FakeAdminSettingsRepository(send_limit_per_hour=3)
        use_case = SendMail(
            mail_service=self.mail_service,
            rate_tracker=FakeRateTracker(),
            settings_repo=low_limit_settings,
        )
        for _ in range(3):
            await self._send(use_case)
        with pytest.raises(MailRateLimitedError):
            await self._send(use_case)
        assert len(self.mail_service.sent) == 3

    async def test_the_configured_lock_minutes_is_what_gets_passed_to_the_tracker(self):
        """Proves send_lock_minutes (not a fixed constant) drives how long
        the tracker locks the scope once the limit is crossed."""
        tracker = FakeRateTracker()
        settings = FakeAdminSettingsRepository(send_limit_per_hour=1, send_lock_minutes=15)
        use_case = SendMail(
            mail_service=self.mail_service, rate_tracker=tracker, settings_repo=settings
        )

        await self._send(use_case)
        with pytest.raises(MailRateLimitedError):
            await self._send(use_case)

        assert tracker.locks["mail:42"] == 15 * 60


# ── HTML sanitization ────────────────────────────────────────────────
#
# The frontend already escapes/sanitizes what a user sees before this is
# ever POSTed, but this use case is the last point before an arbitrary
# html_body reaches SMTP, and nothing upstream is trusted, see
# mail_html_sanitizer.py's docstring.


class TestSendMailSanitization:
    def setup_method(self):
        self.mail_service = FakeMailService()
        self.tracker = FakeRateTracker()
        self.settings = FakeAdminSettingsRepository()
        self.use_case = SendMail(
            mail_service=self.mail_service, rate_tracker=self.tracker, settings_repo=self.settings
        )
        self.actor = make_user()

    async def test_strips_script_tags(self):
        await self.use_case.execute(
            self.actor,
            to="x@example.com",
            subject="Hi",
            html_body="<p>Hi</p><script>alert(document.cookie)</script>",
        )
        sent_body = self.mail_service.sent[0]["html_body"]
        assert "<script" not in sent_body
        assert "<p>Hi</p>" in sent_body

    async def test_strips_event_handler_attributes(self):
        await self.use_case.execute(
            self.actor,
            to="x@example.com",
            subject="Hi",
            html_body='<img src=x onerror="alert(1)">',
        )
        sent_body = self.mail_service.sent[0]["html_body"]
        assert "onerror" not in sent_body

    async def test_keeps_basic_formatting_and_table_markup(self):
        html = (
            "<p>Dear <strong>Supplier</strong>,</p>"
            '<table style="border-collapse:collapse"><tbody><tr>'
            '<td style="padding:4px">Widget</td></tr></tbody></table>'
        )
        await self.use_case.execute(self.actor, to="x@example.com", subject="Hi", html_body=html)
        sent_body = self.mail_service.sent[0]["html_body"]
        assert "<strong>Supplier</strong>" in sent_body
        assert "<table" in sent_body
        assert 'style="padding:4px"' in sent_body
