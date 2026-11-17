"""
POST /admin/settings/mail/test: the endpoint has no catch-all, so a
non-SMTP failure is never labelled an SMTP error and str(exc) never
reaches the client-visible detail. SendTestMail can only raise
InsufficientPermissionsError (403), MailNotEnabledError or
MailNotConfiguredError (400) or SmtpDeliveryError from SmtpMailService
(502), all mapped in exception_handlers, and anything else propagates to
UnhandledExceptionMiddleware's generic 500.
"""

import pytest

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.platform.adapters.inbound.api.deps.services import get_mail_service
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.exceptions import SmtpDeliveryError
from src.modules.platform.domain.value_objects.permission import Permission

BASE = "/api/v1/web/admin/settings/mail/test"
PAYLOAD = {"to": "recipient@example.com"}


class FakeMailService:
    """send_test_mail either raises `outcome` or records the recipient."""

    def __init__(self, outcome: Exception | None = None) -> None:
        self.outcome = outcome
        self.sent_to: list[str] = []

    async def send_test_mail(self, to: str) -> None:
        if self.outcome is not None:
            raise self.outcome
        self.sent_to.append(to)

    # Unused by this endpoint, present only to satisfy IMailService.
    async def send_welcome(self, *args, **kwargs) -> None: ...
    async def send_custom(self, *args, **kwargs) -> None: ...
    async def send_notification_digest(self, *args, **kwargs) -> None: ...


async def _seed_mail(db, *, enabled: bool = True) -> None:
    """SendTestMail checks mail.enabled/host/user/password before ever
    reaching the mail service. Seed a fully-configured setup so the fake
    service (overridden per-test below) is what actually decides the
    outcome, except in the enabled=False case which never reaches it."""
    await SqlAlchemyAdminSettingsRepository(db).save_mail(
        AdminMailSettings(
            id=1,
            enabled=enabled,
            host="smtp.example.com",
            port=587,
            user="glados@example.com",
            password="hunter2",
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


@pytest.fixture
async def mail_service(db):
    """Overrides get_mail_service with a fake for the duration of the
    test; the specific outcome is set by assigning `.outcome` before the
    request, or by re-pointing the override (see tests below)."""
    await _seed_mail(db, enabled=True)
    fake = FakeMailService()
    app.dependency_overrides[get_mail_service] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_mail_service, None)


@pytest.fixture
async def sender(auth_client):
    return await auth_client(permissions=[Permission.WRITE_SETTINGS])


class TestRealSmtpFailureIsA502:
    async def test_smtp_delivery_error_is_502_with_its_own_message(self, sender, mail_service):
        mail_service.outcome = SmtpDeliveryError("Connection refused")

        response = await sender.post(BASE, json=PAYLOAD)

        # Hand-rolled HTTPException (caught locally here, never reaches
        # domain_error_handler), so no "code" field, just detail=str(exc).
        assert response.status_code == 502
        assert response.json() == {"detail": "Connection refused", "code": "SmtpDeliveryError"}


class TestMailConfigErrorIsA400:
    async def test_mail_not_enabled_is_400(self, sender, db):
        await _seed_mail(db, enabled=False)

        response = await sender.post(BASE, json=PAYLOAD)

        assert response.status_code == 400
        assert response.json() == {"detail": "Mail is not enabled.", "code": "MailNotEnabledError"}


class TestUnexpectedFailureIsAGeneric500:
    async def test_an_unexpected_exception_is_a_generic_500_not_an_smtp_error(
        self, sender, mail_service
    ):
        """A failure that is not SMTP-related at all is a generic 500, not
        a 502 whose body is `f"SMTP error: {exc}"` leaking the raw
        exception text."""
        mail_service.outcome = RuntimeError("secret-db-dsn")

        response = await sender.post(BASE, json=PAYLOAD)

        assert response.status_code == 500
        assert "SMTP error" not in response.text
        assert "secret-db-dsn" not in response.text
        assert response.json() == {"detail": "Internal server error", "code": "InternalError"}


class TestPermissionGate:
    async def test_actor_without_write_settings_gets_403_not_502(self, auth_client, mail_service):
        """The InsufficientPermissionsError mapping applies, so a missing
        permission is a 403 and never a 502 that reports the missing
        write:settings permission as an "SMTP error"."""
        no_permissions = await auth_client(permissions=[])

        response = await no_permissions.post(BASE, json=PAYLOAD)

        assert response.status_code == 403
        assert response.json()["code"] == "InsufficientPermissionsError"


class TestHappyPath:
    async def test_a_working_mail_service_returns_204(self, sender, mail_service):
        response = await sender.post(BASE, json=PAYLOAD)

        assert response.status_code == 204
        assert mail_service.sent_to == ["recipient@example.com"]
