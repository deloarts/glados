"""
Unit tests for SmtpMailService, starting with its certificate verification wiring.
No network: aiosmtplib.SMTP is monkeypatched inside the adapter module, and
the fake records exactly what it was constructed and called with so a test
can assert on the concrete ssl.SSLContext values rather than trusting "is
the default", see smtp_mail_service._smtp.
"""

import email
import ssl
from types import SimpleNamespace
from typing import ClassVar

import pytest
from jinja2 import TemplateSyntaxError

from src.modules.platform.adapters.outbound.external.mail import smtp_mail_service as mod
from src.modules.platform.adapters.outbound.external.mail.smtp_mail_service import SmtpMailService
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailTemplate
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind


def make_mail(**kwargs) -> AdminMailSettings:
    defaults = dict(
        id=1,
        enabled=True,
        host="smtp.example.com",
        port=587,
        user="noreply",
        password="secret",
        from_address="noreply@example.com",
        use_tls=True,
        use_ssl=False,
        verify_certificate=True,
        from_display_name="",
        reply_to=None,
        send_limit_per_hour=20,
        send_lock_minutes=60,
        alert_recipients=[],
    )
    defaults.update(kwargs)
    return AdminMailSettings(**defaults)


class FakeSMTP:
    """Records the raw args/kwargs it was constructed with. Like
    aiosmtplib.SMTP, it negotiates STARTTLS itself on connect when built
    with start_tls=True, using the tls_context it was given."""

    instances: ClassVar[list["FakeSMTP"]] = []

    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self.starttls_context: object | None = None
        self.starttls_called = False
        self.login_calls: list[tuple[str, str]] = []
        self.sendmail_calls: list[tuple[str, object, str]] = []
        FakeSMTP.instances.append(self)

    async def login(self, user: str, password: str) -> None:
        self.login_calls.append((user, password))

    async def sendmail(self, sender, recipients, msg) -> None:
        self.sendmail_calls.append((sender, recipients, msg))

    async def __aenter__(self) -> "FakeSMTP":
        if self.kwargs.get("start_tls"):
            self.starttls_called = True
            self.starttls_context = self.kwargs.get("tls_context")
        return self

    async def __aexit__(self, *exc_info) -> bool:
        return False


@pytest.fixture(autouse=True)
def _reset_fakes(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(mod.aiosmtplib, "SMTP", FakeSMTP)
    yield


async def test_the_read_transaction_ends_before_the_smtp_connection_opens(monkeypatch):
    class RecordingUow:
        commits_before_connect: int | None = None
        commits = 0

        async def commit(self):
            self.commits += 1

        async def rollback(self):
            pass

    uow = RecordingUow()
    original_enter = FakeSMTP.__aenter__

    async def recording_enter(self):
        uow.commits_before_connect = uow.commits
        return await original_enter(self)

    monkeypatch.setattr(FakeSMTP, "__aenter__", recording_enter)
    await SmtpMailService(make_mail(), uow=uow).send_test_mail("a@b.com")

    assert uow.commits_before_connect == 1


async def test_verify_on_uses_a_verifying_context():
    """verify_certificate=True over implicit TLS (use_tls): the context is
    left at ssl.create_default_context()'s own secure defaults."""
    await SmtpMailService(make_mail(verify_certificate=True, use_ssl=True)).send_test_mail(
        "a@b.com"
    )

    (instance,) = FakeSMTP.instances
    ctx = instance.kwargs["tls_context"]
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED


async def test_verify_off_disables_verification():
    """verify_certificate=False is the explicit opt-out for a relay whose
    certificate cannot be verified: both hostname and chain validation are
    switched off."""
    await SmtpMailService(make_mail(verify_certificate=False, use_ssl=True)).send_test_mail(
        "a@b.com"
    )

    (instance,) = FakeSMTP.instances
    ctx = instance.kwargs["tls_context"]
    assert ctx.check_hostname is False
    assert ctx.verify_mode == ssl.CERT_NONE


async def test_starttls_gets_the_same_context():
    """use_ssl=False, use_tls=True: the plain SMTP connection is upgraded
    via STARTTLS, and the same verifying context is what's passed to it."""
    await SmtpMailService(
        make_mail(verify_certificate=True, use_ssl=False, use_tls=True)
    ).send_test_mail("a@b.com")

    (instance,) = FakeSMTP.instances
    assert instance.starttls_called is True
    assert instance.starttls_context is not None
    assert instance.starttls_context.check_hostname is True
    assert instance.starttls_context.verify_mode == ssl.CERT_REQUIRED


async def test_plain_connection_does_not_use_a_context():
    """use_ssl=False, use_tls=False: a fully plaintext relay. The flag must
    not be able to break it. aiosmtplib always receives a tls_context, but
    with neither implicit TLS nor STARTTLS enabled the connection never
    negotiates TLS, so the context has no meaning for it."""
    await SmtpMailService(
        make_mail(verify_certificate=False, use_ssl=False, use_tls=False)
    ).send_test_mail("a@b.com")

    (instance,) = FakeSMTP.instances
    assert instance.kwargs["use_tls"] is False
    assert instance.kwargs["start_tls"] is False
    assert instance.starttls_called is False


# ── §1 fallback chain (_render) ──────────────────────────────────────


class FakeSettingsRepo:
    """Minimal IAdminSettingsRepository stand-in: SmtpMailService._render
    only ever calls get_general() (for the tenant default language) and
    list_mail_templates() (for the admin-configured rows)."""

    def __init__(
        self,
        templates: list[AdminMailTemplate] | None = None,
        default_language: Language = Language.enGB,
        general_raises: bool = False,
    ) -> None:
        self._templates = templates or []
        self._default_language = default_language
        self._general_raises = general_raises

    async def get_general(self) -> SimpleNamespace:
        if self._general_raises:
            raise RuntimeError("Admin general settings not seeded, run InitDatabase first.")
        return SimpleNamespace(default_language=self._default_language)

    async def list_mail_templates(self) -> list[AdminMailTemplate]:
        return list(self._templates)


def _row(kind: str, language: str, subject: str = "", body: str = "") -> AdminMailTemplate:
    return AdminMailTemplate(
        id=1,
        kind=MailTemplateKind(kind),
        language=Language(language),
        subject=subject,
        body=body,
    )


def _sent_message(instance: FakeSMTP) -> email.message.Message:
    (_, _, raw) = instance.sendmail_calls[0]
    return email.message_from_string(raw)


def _sent_html(instance: FakeSMTP) -> str:
    """The rendered HTML body, decoded. MIMEText(..., "utf-8") transfer-
    encodes the payload (base64 here, since email.mime.text always picks
    a non-identity encoding for a non-us-ascii charset), so a raw
    substring match against `msg.as_string()` would never find plain
    text even when it is right there in the (encoded) body."""
    msg = _sent_message(instance)
    part = msg.get_payload(0) if msg.is_multipart() else msg
    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")


def _sent_subject(instance: FakeSMTP) -> str:
    return _sent_message(instance)["Subject"]


class TestLanguageFallbackChain:
    async def test_deAT_row_is_used_when_recipient_language_is_deAT(self):
        repo = FakeSettingsRepo(
            templates=[
                _row(
                    "welcome",
                    "deAT",
                    subject="Welcome (deAT row)",
                    body="<p>Greetings {{ full_name }}</p>",
                )
            ]
        )
        service = SmtpMailService(
            make_mail(), settings_repo=repo, domain="https://glados.example.com"
        )

        await service.send_welcome(
            email="a@b.com",
            full_name="Jamie",
            username="jamie",
            created_by_name="Alex",
            created_by_email="alex@example.com",
            language=Language.deAT,
        )

        (instance,) = FakeSMTP.instances
        assert "Greetings Jamie" in _sent_html(instance)
        assert _sent_subject(instance) == "Welcome (deAT row)"

    async def test_unconfigured_deAT_falls_back_to_the_enGB_row(self):
        """A blank body (a seeded-empty, never-translated row) is treated
        as absent, not as an empty template to send."""
        repo = FakeSettingsRepo(
            templates=[
                _row("welcome", "deAT", subject="", body=""),
                _row("welcome", "enGB", subject="Welcome", body="<p>Hi {{ full_name }}</p>"),
            ]
        )
        service = SmtpMailService(make_mail(), settings_repo=repo)

        await service.send_welcome(
            email="a@b.com",
            full_name="Jamie",
            username="jamie",
            created_by_name="Alex",
            created_by_email="alex@example.com",
            language=Language.deAT,
        )

        (instance,) = FakeSMTP.instances
        assert "Hi Jamie" in _sent_html(instance)

    async def test_no_settings_repo_falls_to_the_packaged_file_in_the_recipients_language(self):
        """The SmtpMailService(make_mail(...)) calls this module makes above
        construct with no settings_repo at all. That must still send
        something sane: the packaged template of the recipient's language,
        with the file's title as the subject."""
        service = SmtpMailService(make_mail())

        await service.send_welcome(
            email="a@b.com",
            full_name="Jamie",
            username="jamie",
            created_by_name="Alex",
            created_by_email="alex@example.com",
            language=Language.deAT,
        )

        (instance,) = FakeSMTP.instances
        assert "Hallo Jamie" in _sent_html(instance)
        assert _sent_subject(instance) == "Willkommen bei Glados"

    async def test_no_stored_templates_and_no_language_send_the_packaged_engb_file(self):
        service = SmtpMailService(make_mail(), settings_repo=FakeSettingsRepo())

        await service.send_welcome(
            email="a@b.com",
            full_name="Jamie",
            username="jamie",
            created_by_name="Alex",
            created_by_email="alex@example.com",
        )

        (instance,) = FakeSMTP.instances
        assert "Hi Jamie" in _sent_html(instance)
        assert _sent_subject(instance) == "Welcome to Glados"

    async def test_get_general_raising_runtime_error_falls_through_to_the_floor(self):
        """An unseeded install's get_general() raises RuntimeError rather
        than inventing a default. _render must catch it and still send,
        not blow up a welcome mail over a startup-ordering detail."""
        repo = FakeSettingsRepo(
            templates=[_row("welcome", "enGB", subject="Hi", body="<p>Hi {{ full_name }}</p>")],
            general_raises=True,
        )
        service = SmtpMailService(make_mail(), settings_repo=repo)

        await service.send_welcome(
            email="a@b.com",
            full_name="Jamie",
            username="jamie",
            created_by_name="Alex",
            created_by_email="alex@example.com",
        )

        (instance,) = FakeSMTP.instances
        assert "Hi Jamie" in _sent_html(instance)


class TestDomainInjection:
    async def test_domain_renders_into_every_system_mail_context(self):
        service = SmtpMailService(make_mail(), domain="https://custom.example.org")
        await service.send_test_mail("a@b.com")

        (instance,) = FakeSMTP.instances
        assert "https://custom.example.org" in _sent_html(instance)


class TestSubjectFromRow:
    async def test_subject_comes_from_the_stored_row_rendered_through_jinja(self):
        repo = FakeSettingsRepo(
            templates=[
                _row(
                    "welcome",
                    "enGB",
                    subject="Welcome, {{ full_name }}!",
                    body="<p>Hi {{ full_name }}</p>",
                )
            ]
        )
        service = SmtpMailService(make_mail(), settings_repo=repo)

        await service.send_welcome(
            email="a@b.com",
            full_name="Jamie",
            username="jamie",
            created_by_name="Alex",
            created_by_email="alex@example.com",
        )

        (instance,) = FakeSMTP.instances
        assert _sent_subject(instance) == "Welcome, Jamie!"

    async def test_a_blank_subject_falls_back_to_the_spec_default(self):
        repo = FakeSettingsRepo(
            templates=[_row("welcome", "enGB", subject="", body="<p>Hi {{ full_name }}</p>")]
        )
        service = SmtpMailService(make_mail(), settings_repo=repo)

        await service.send_welcome(
            email="a@b.com",
            full_name="Jamie",
            username="jamie",
            created_by_name="Alex",
            created_by_email="alex@example.com",
        )

        (instance,) = FakeSMTP.instances
        assert _sent_subject(instance) == "Welcome to Glados"


class TestBrokenStoredTemplateRaises:
    async def test_bad_jinja_syntax_in_the_stored_row_propagates(self):
        """create_user.py's try/except around send_welcome is what
        swallows this (see test_user_use_cases.py). The mail service
        itself must not silently eat it, or a broken admin edit would
        look like a successfully delivered mail."""
        repo = FakeSettingsRepo(
            templates=[_row("welcome", "enGB", subject="Hi", body="<p>{% if %}</p>")]
        )
        service = SmtpMailService(make_mail(), settings_repo=repo)

        with pytest.raises(TemplateSyntaxError):
            await service.send_welcome(
                email="a@b.com",
                full_name="Jamie",
                username="jamie",
                created_by_name="Alex",
                created_by_email="alex@example.com",
            )


class TestSendSystemMail:
    """The generic send used by HandleEventNotifications' four event-mail
    kinds (account_deactivated/permissions_changed/project_assigned/
    product_assigned), with no bespoke method per kind. See
    IMailService.send_system_mail's docstring."""

    async def test_deAT_row_is_used_when_configured(self):
        repo = FakeSettingsRepo(
            templates=[
                _row(
                    "account_deactivated",
                    "deAT",
                    subject="Account deactivated (deAT row)",
                    body="<p>Greetings {{ full_name }}</p>",
                )
            ]
        )
        service = SmtpMailService(make_mail(), settings_repo=repo)

        await service.send_system_mail(
            MailTemplateKind.ACCOUNT_DEACTIVATED,
            to="jamie@example.com",
            language=Language.deAT,
            full_name="Jamie",
        )

        (instance,) = FakeSMTP.instances
        assert _sent_subject(instance) == "Account deactivated (deAT row)"
        assert "Jamie" in _sent_html(instance)

    async def test_falls_back_to_the_packaged_file_of_the_language_with_no_repo(self):
        service = SmtpMailService(make_mail(), domain="https://glados.example.com")

        await service.send_system_mail(
            MailTemplateKind.ACCOUNT_DEACTIVATED,
            to="jamie@example.com",
            language=Language.deAT,
            full_name="Jamie",
        )

        (instance,) = FakeSMTP.instances
        assert _sent_subject(instance) == "Dein Glados-Konto wurde deaktiviert"
        assert "Jamie" in _sent_html(instance)

    async def test_extra_context_reaches_the_template(self):
        service = SmtpMailService(make_mail())

        await service.send_system_mail(
            MailTemplateKind.PROJECT_ASSIGNED,
            to="jamie@example.com",
            full_name="Jamie",
            project_number="P-2026-0007",
        )

        (instance,) = FakeSMTP.instances
        assert "P-2026-0007" in _sent_html(instance)


class TestOpsAlerts:
    """send_schedule_error / send_disc_space_warning log and also fan out
    to every mail.alert_recipients address."""

    async def test_schedule_error_fans_out_to_every_alert_recipient(self):
        service = SmtpMailService(
            make_mail(alert_recipients=["ops1@example.com", "ops2@example.com"])
        )

        await service.send_schedule_error("Nightly Auto-Plan", "boom")

        assert len(FakeSMTP.instances) == 2
        recipients = [i.sendmail_calls[0][1] for i in FakeSMTP.instances]
        assert recipients == ["ops1@example.com", "ops2@example.com"]
        assert "Nightly Auto-Plan" in _sent_html(FakeSMTP.instances[0])
        assert "boom" in _sent_html(FakeSMTP.instances[0])

    async def test_disk_space_warning_fans_out_with_its_own_context(self):
        service = SmtpMailService(make_mail(alert_recipients=["ops1@example.com"]))

        await service.send_disc_space_warning(42.5, 50.0)

        (instance,) = FakeSMTP.instances
        html = _sent_html(instance)
        assert "42.5" in html
        assert "50.0" in html

    async def test_empty_alert_recipients_is_a_silent_no_op(self):
        service = SmtpMailService(make_mail(alert_recipients=[]))

        await service.send_schedule_error("Task", "boom")

        assert FakeSMTP.instances == []

    async def test_mail_disabled_is_a_no_op_even_with_recipients_configured(self):
        service = SmtpMailService(make_mail(enabled=False, alert_recipients=["ops1@example.com"]))

        await service.send_disc_space_warning(1.0, 2.0)

        assert FakeSMTP.instances == []

    async def test_a_delivery_failure_to_one_recipient_does_not_block_the_others(self, monkeypatch):
        class FlakySMTP(FakeSMTP):
            async def sendmail(self, sender, recipients, msg):
                if recipients == "bad@example.com":
                    raise mod.aiosmtplib.SMTPException("mailbox unavailable")
                await super().sendmail(sender, recipients, msg)

        monkeypatch.setattr(mod.aiosmtplib, "SMTP", FlakySMTP)

        service = SmtpMailService(
            make_mail(alert_recipients=["bad@example.com", "good@example.com"])
        )

        await service.send_schedule_error("Task", "boom")  # must not raise

        assert len(FakeSMTP.instances) == 2
        assert FakeSMTP.instances[0].sendmail_calls == []  # the failed attempt
        assert len(FakeSMTP.instances[1].sendmail_calls) == 1  # the one that got through


# ── Mail identity (From display name + Reply-To) ────────────────────


class TestMailIdentity:
    """from_display_name/reply_to (Settings polish batch): the From header
    wraps the sender address in the configured display name, and a
    configured Reply-To is applied whenever the caller supplies none."""

    async def test_from_header_includes_the_configured_display_name(self):
        service = SmtpMailService(make_mail(from_display_name="Glados Notifications"))
        await service.send_test_mail("a@b.com")

        (instance,) = FakeSMTP.instances
        assert _sent_message(instance)["From"] == "Glados Notifications <noreply@example.com>"

    async def test_from_header_is_the_bare_address_when_no_display_name_is_configured(self):
        """ "" (the shipped default) means no display name: the bare
        address is sent as is."""
        service = SmtpMailService(make_mail(from_display_name=""))
        await service.send_test_mail("a@b.com")

        (instance,) = FakeSMTP.instances
        assert _sent_message(instance)["From"] == "noreply@example.com"

    async def test_from_header_applies_to_send_custom_too(self):
        service = SmtpMailService(make_mail(from_display_name="Glados"))
        await service.send_custom(to="a@b.com", subject="Hi", html_body="<p>hi</p>")

        (instance,) = FakeSMTP.instances
        assert _sent_message(instance)["From"] == "Glados <noreply@example.com>"

    async def test_send_custom_reaches_every_recipient_of_the_to_field(self):
        service = SmtpMailService(make_mail())
        await service.send_custom(
            to="karin@example.com, martin@example.com",
            subject="Order",
            html_body="<p>hi</p>",
            cc="me@example.com",
        )

        (instance,) = FakeSMTP.instances
        (_, recipients, _) = instance.sendmail_calls[0]
        assert recipients == ["karin@example.com", "martin@example.com", "me@example.com"]
        assert _sent_message(instance)["To"] == "karin@example.com, martin@example.com"

    async def test_configured_reply_to_is_applied_when_the_caller_supplies_none(self):
        service = SmtpMailService(make_mail(reply_to="support@example.com"))
        await service.send_custom(to="a@b.com", subject="Hi", html_body="<p>hi</p>")

        (instance,) = FakeSMTP.instances
        assert _sent_message(instance)["Reply-To"] == "support@example.com"

    async def test_the_callers_own_reply_to_wins_over_the_configured_default(self):
        service = SmtpMailService(make_mail(reply_to="support@example.com"))
        await service.send_custom(
            to="a@b.com", subject="Hi", html_body="<p>hi</p>", reply_to="caller@example.com"
        )

        (instance,) = FakeSMTP.instances
        assert _sent_message(instance)["Reply-To"] == "caller@example.com"

    async def test_no_reply_to_header_when_none_is_configured_or_supplied(self):
        service = SmtpMailService(make_mail(reply_to=None))
        await service.send_custom(to="a@b.com", subject="Hi", html_body="<p>hi</p>")

        (instance,) = FakeSMTP.instances
        assert _sent_message(instance)["Reply-To"] is None

    async def test_system_mail_also_gets_the_configured_reply_to(self):
        """_send (welcome/system/digest/test mails) has no per-call reply_to
        parameter at all, so the configured default is the only source."""
        service = SmtpMailService(make_mail(reply_to="ops@example.com"))
        await service.send_test_mail("a@b.com")

        (instance,) = FakeSMTP.instances
        assert _sent_message(instance)["Reply-To"] == "ops@example.com"
