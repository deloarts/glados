"""
Unit tests for the mail and LDAP probe/template use cases: TestSendTestMail,
TestVerifyLdapConnection, TestGetMailTemplates, TestUpdateMailTemplates and
TestPreviewMailTemplate. No database, no HTTP. All dependencies replaced
with in-memory fakes.
"""

import pytest

from src.modules.platform.adapters.outbound.external.mail.render import render_string
from src.modules.platform.application.dto.admin_settings_dto.auth import VerifyLdapConnectionCommand
from src.modules.platform.application.dto.admin_settings_dto.mail import MailTemplateEntryCommand
from src.modules.platform.application.dto.admin_settings_dto.mail import UpdateMailTemplatesCommand
from src.modules.platform.application.use_cases.admin_settings.get_mail_templates import (
    GetMailTemplates,
)
from src.modules.platform.application.use_cases.admin_settings.preview_mail_template import (
    PreviewMailTemplate,
)
from src.modules.platform.application.use_cases.admin_settings.send_test_mail import SendTestMail
from src.modules.platform.application.use_cases.admin_settings.update_mail_templates import (
    UpdateMailTemplates,
)
from src.modules.platform.application.use_cases.admin_settings.verify_ldap_connection import (
    VerifyLdapConnection,
)
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailTemplate
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import LdapAuthenticationFailedError
from src.modules.platform.domain.exceptions import LdapNotConfiguredError
from src.modules.platform.domain.exceptions import LdapUnavailableError
from src.modules.platform.domain.exceptions import MailNotConfiguredError
from src.modules.platform.domain.exceptions import MailNotEnabledError
from src.modules.platform.domain.exceptions import MailTemplateRenderError
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.admin_settings.fakes import FakeAdminSettingsRepository
from tests.unit.fakes import FakeUnitOfWork


class FakeMailService:
    def __init__(self) -> None:
        self.sent_test_mails: list[str] = []

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

    async def send_custom(self, to, subject, html_body, cc=None, reply_to=None) -> None:
        raise NotImplementedError

    async def send_test_mail(self, to: str) -> None:
        self.sent_test_mails.append(to)


class FakeLdapAuthenticator:
    def __init__(self, verdict: bool | Exception = True) -> None:
        self.verdict = verdict
        self.settings = None
        self.calls: list[tuple[str, str]] = []

    async def authenticate(self, username: str, password: str) -> bool:
        self.calls.append((username, password))
        if isinstance(self.verdict, Exception):
            raise self.verdict
        return self.verdict


class TestSendTestMail:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.repo.mail.enabled = True
        self.repo.mail.host = "smtp.example.com"
        self.repo.mail.user = "noreply"
        self.repo.mail.password = "secret"
        self.mail_service = FakeMailService()
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = SendTestMail(self.repo, self.mail_service)

    async def test_sends_successfully(self):
        await self.use_case.execute(actor=self.actor, to="test@example.com")
        assert self.mail_service.sent_test_mails == ["test@example.com"]

    async def test_mail_not_enabled_raises(self):
        self.repo.mail.enabled = False
        with pytest.raises(MailNotEnabledError):
            await self.use_case.execute(actor=self.actor, to="test@example.com")

    async def test_mail_not_configured_raises(self):
        self.repo.mail.password = None
        with pytest.raises(MailNotConfiguredError):
            await self.use_case.execute(actor=self.actor, to="test@example.com")

    async def test_unprivileged_cannot_send(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, to="test@example.com")


class TestVerifyLdapConnection:
    def setup_method(self):
        self.ldap = FakeLdapAuthenticator()
        self.built_with: list = []

        def factory(settings):
            self.built_with.append(settings)
            return self.ldap

        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = VerifyLdapConnection(factory)

    def _cmd(self, **kwargs) -> VerifyLdapConnectionCommand:
        defaults = dict(
            ldap_host="dc-01.example.com",
            ldap_domain="EXAMPLE",
            username="admin",
            password="secret",
        )
        defaults.update(kwargs)
        return VerifyLdapConnectionCommand(**defaults)

    async def test_successful_bind_does_not_raise(self):
        self.ldap.verdict = True
        await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert self.ldap.calls == [("admin", "secret")]

    async def test_the_read_transaction_ends_before_the_bind(self):
        ldap = self.ldap

        class RecordingUow:
            calls_at_commit: int | None = None

            async def commit(self):
                self.calls_at_commit = len(ldap.calls)

            async def rollback(self):
                pass

        uow = RecordingUow()
        await VerifyLdapConnection(lambda settings: ldap, uow=uow).execute(
            actor=self.actor, cmd=self._cmd()
        )

        assert uow.calls_at_commit == 0
        assert ldap.calls == [("admin", "secret")]

    async def test_rejected_credentials_raise_authentication_failed(self):
        self.ldap.verdict = False
        with pytest.raises(LdapAuthenticationFailedError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd())

    async def test_unreachable_directory_propagates(self):
        """Must stay distinguishable from a rejection, they map to different
        status codes and mean very different things to an admin."""
        self.ldap.verdict = LdapUnavailableError("dc unreachable")
        with pytest.raises(LdapUnavailableError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd())

    async def test_missing_password_is_a_configuration_error(self):
        with pytest.raises(LdapNotConfiguredError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(password=""))

    async def test_missing_username_is_a_configuration_error(self):
        with pytest.raises(LdapNotConfiguredError):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(username="   "))

    async def test_probes_with_the_supplied_settings_not_the_stored_ones(self):
        await self.use_case.execute(actor=self.actor, cmd=self._cmd(ldap_host="other.example.com"))
        assert self.built_with[0].ldap_host == "other.example.com"

    async def test_probes_even_when_ldap_is_switched_off(self):
        """The whole point is validating a configuration before enabling it."""
        await self.use_case.execute(actor=self.actor, cmd=self._cmd(ldap_enabled=False))
        assert self.built_with[0].ldap_enabled is True

    async def test_unprivileged_cannot_probe(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())


class TestGetMailTemplates:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.READ_SETTINGS])
        self.use_case = GetMailTemplates(self.repo)

    async def test_returns_every_kind_even_with_no_rows_stored(self):
        """Every MailTemplateKind gets a group in the response, driven by
        the spec registry, not by whatever rows happen to exist."""
        result = await self.use_case.execute(actor=self.actor)
        kinds = {group.kind for group in result.kinds}
        assert kinds == set(MailTemplateKind)

    async def test_a_stored_row_is_reflected_in_its_kind_group(self):
        await self.repo.save_mail_template(
            AdminMailTemplate(
                id=0,
                kind=MailTemplateKind.WELCOME,
                language=Language.enGB,
                subject="Hi",
                body="<p>Hi</p>",
            )
        )
        result = await self.use_case.execute(actor=self.actor)
        welcome = next(g for g in result.kinds if g.kind == MailTemplateKind.WELCOME)
        assert len(welcome.entries) == 1
        assert welcome.entries[0].language == Language.enGB
        assert welcome.entries[0].configured is True

    async def test_unprivileged_cannot_read(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor)


class TestUpdateMailTemplates:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = UpdateMailTemplates(self.repo, uow=FakeUnitOfWork())

    def _cmd(self, **kwargs) -> UpdateMailTemplatesCommand:
        defaults = dict(
            kind=MailTemplateKind.WELCOME,
            entries=[
                MailTemplateEntryCommand(
                    language=Language.enGB, subject="Welcome", body="<p>Hi {{ full_name }}</p>"
                )
            ],
        )
        defaults.update(kwargs)
        return UpdateMailTemplatesCommand(**defaults)

    @staticmethod
    def _entry(language: Language, tag: str) -> MailTemplateEntryCommand:
        return MailTemplateEntryCommand(language=language, subject=tag, body=f"<p>{tag}</p>")

    async def test_saves_every_entry_for_the_kind(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=self._cmd(
                entries=[self._entry(Language.enGB, "EN"), self._entry(Language.deAT, "DE")]
            ),
        )
        assert {e.language for e in result.entries} == {Language.enGB, Language.deAT}
        assert len(self.repo.mail_templates) == 2

    async def test_second_save_updates_rather_than_duplicates(self):
        await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        await self.use_case.execute(
            actor=self.actor,
            cmd=self._cmd(
                entries=[
                    MailTemplateEntryCommand(
                        language=Language.enGB, subject="Updated", body="<p>Updated</p>"
                    )
                ]
            ),
        )
        assert len(self.repo.mail_templates) == 1
        assert self.repo.mail_templates[0].subject == "Updated"

    async def test_appends_exactly_one_audit_entry(self):
        """Kind-scoped: every language entry in the same call is one audit
        entry, not one per row."""
        await self.use_case.execute(
            actor=self.actor,
            cmd=self._cmd(
                entries=[self._entry(Language.enGB, "EN"), self._entry(Language.deAT, "DE")]
            ),
        )
        assert len(self.repo.audit_log) == 1
        assert self.repo.audit_log[0].settings_domain == "mail"

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())


class TestPreviewMailTemplate:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.READ_SETTINGS])
        self.use_case = PreviewMailTemplate(render_string)

    async def test_renders_the_draft_against_the_kind_sample_context(self):
        result = await self.use_case.execute(
            actor=self.actor,
            kind=MailTemplateKind.WELCOME,
            subject="Hi {{ full_name }}",
            body="<p>Hi {{ full_name }}, visit {{ domain }}</p>",
        )
        assert result.subject == "Hi Jamie Appleseed"
        assert "Jamie Appleseed" in result.html
        assert "https://glados.example.com" in result.html

    async def test_bad_jinja_syntax_raises_mail_template_render_error(self):
        with pytest.raises(MailTemplateRenderError):
            await self.use_case.execute(
                actor=self.actor,
                kind=MailTemplateKind.WELCOME,
                subject="Hi",
                body="<p>{% if %}</p>",
            )

    async def test_accessing_an_attribute_of_an_undeclared_variable_raises(self):
        """Jinja's default Undefined silently renders a bare
        `{{ not_declared }}` as an empty string and a `{% for %}` over one
        as zero iterations: neither raises. Accessing an *attribute* of
        an undefined value does, via Undefined.__getattr__, which is the
        shape the digest template's `item.reason` would hit if `items`
        were ever missing from the context entirely."""
        with pytest.raises(MailTemplateRenderError):
            await self.use_case.execute(
                actor=self.actor,
                kind=MailTemplateKind.WELCOME,
                subject="Hi",
                body="{{ not_declared.attr }}",
            )

    async def test_unprivileged_cannot_preview(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(
                actor=actor, kind=MailTemplateKind.WELCOME, subject="Hi", body="Hi"
            )
