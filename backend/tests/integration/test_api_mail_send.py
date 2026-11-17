"""
send:mail permission gate and per-user rate limit on POST /mail/send,
see SendMail / mail_policy.py. Both the mail service and the rate tracker
are overridden with fakes: this must never attempt a real SMTP connection,
and the rate-limit boundary test needs a tracker it can inspect. The rate
limit itself is admin-configurable (AdminMailSettings.send_limit_per_hour/
send_lock_minutes); a fake settings repo stands in for the real one so the
boundary test doesn't depend on whatever's actually seeded in the DB.
"""

from collections.abc import Iterator

import pytest

from src.bootstrap.main import app
from src.modules.platform.adapters.inbound.api.deps.misc import get_send_mail_use_case
from src.modules.platform.application.use_cases.mail.send_mail import SendMail
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration.fakes import FakeLoginAttemptTracker

SEND_MAIL = [Permission.SEND_MAIL]

PAYLOAD = {"to": "recipient@example.com", "subject": "Hi", "html_body": "<p>hi</p>"}

# Matches AdminMailSettings' shipped default (see the migration and
# init_db's seed).
SEND_LIMIT_PER_HOUR = 20


class FakeMailService:
    def __init__(self) -> None:
        self.sent: list[dict[str, str | None]] = []

    async def send_custom(self, to, subject, html_body, cc=None, reply_to=None) -> None:
        self.sent.append({"to": to, "subject": subject})


class FakeAdminSettingsRepository:
    """Minimal IAdminSettingsRepository stand-in: SendMail only ever calls
    get_mail(), and only reads send_limit_per_hour/send_lock_minutes."""

    def __init__(self, send_limit_per_hour: int = SEND_LIMIT_PER_HOUR) -> None:
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
            send_lock_minutes=60,
            alert_recipients=[],
        )

    async def get_mail(self) -> AdminMailSettings:
        return self._mail


@pytest.fixture
def mail_service() -> FakeMailService:
    return FakeMailService()


@pytest.fixture
def rate_tracker() -> FakeLoginAttemptTracker:
    return FakeLoginAttemptTracker()


@pytest.fixture
def settings_repo() -> FakeAdminSettingsRepository:
    return FakeAdminSettingsRepository()


@pytest.fixture(autouse=True)
def _override_send_mail(mail_service, rate_tracker, settings_repo) -> Iterator[None]:
    """Every test in this file uses the fakes above, a real SmtpMailService
    would attempt a live SMTP connection, and the rate-limit tests need a
    tracker they can assert against."""
    app.dependency_overrides[get_send_mail_use_case] = lambda: SendMail(
        mail_service=mail_service, rate_tracker=rate_tracker, settings_repo=settings_repo
    )
    yield
    app.dependency_overrides.pop(get_send_mail_use_case, None)


@pytest.fixture
async def sender(auth_client):
    return await auth_client(permissions=SEND_MAIL)


class TestSendMailPermission:
    async def test_actor_without_permission_gets_403(self, auth_client, mail_service):
        no_permissions = await auth_client(permissions=[])

        response = await no_permissions.post("/api/v1/web/mail/send", json=PAYLOAD)

        assert response.status_code == 403
        assert response.json()["code"] == "InsufficientPermissionsError"
        assert mail_service.sent == []

    async def test_actor_with_permission_succeeds(self, sender, mail_service):
        response = await sender.post("/api/v1/web/mail/send", json=PAYLOAD)

        assert response.status_code == 204
        assert len(mail_service.sent) == 1
        assert mail_service.sent[0]["to"] == "recipient@example.com"


class TestSendMailRateLimit:
    async def test_the_send_that_crosses_the_limit_gets_429(self, sender, mail_service):
        for _ in range(SEND_LIMIT_PER_HOUR):
            assert (await sender.post("/api/v1/web/mail/send", json=PAYLOAD)).status_code == 204

        response = await sender.post("/api/v1/web/mail/send", json=PAYLOAD)

        assert response.status_code == 429
        assert response.json()["code"] == "MailRateLimitedError"
        assert len(mail_service.sent) == SEND_LIMIT_PER_HOUR

    async def test_a_lower_configured_limit_gates_earlier(self, sender, mail_service, rate_tracker):
        """Proves the limit is read from AdminMailSettings.send_limit_per_hour
        (via the settings repo), not a hard-coded 20: a tenant configured
        with a limit of 2 is gated well before the shipped default would
        kick in."""
        app.dependency_overrides[get_send_mail_use_case] = lambda: SendMail(
            mail_service=mail_service,
            rate_tracker=rate_tracker,
            settings_repo=FakeAdminSettingsRepository(send_limit_per_hour=2),
        )

        assert (await sender.post("/api/v1/web/mail/send", json=PAYLOAD)).status_code == 204
        assert (await sender.post("/api/v1/web/mail/send", json=PAYLOAD)).status_code == 204

        response = await sender.post("/api/v1/web/mail/send", json=PAYLOAD)

        assert response.status_code == 429
        assert len(mail_service.sent) == 2
