"""
Maps the SMTP mail settings and the localized mail templates to result DTOs.
The SMTP password is replaced with a boolean presence flag.
"""

from src.modules.platform.application.dto.admin_settings_dto.mail import AdminMailSettingsResult
from src.modules.platform.application.dto.admin_settings_dto.mail import AdminMailTemplateResult
from src.modules.platform.application.dto.admin_settings_dto.mail import AdminMailTemplatesResult
from src.modules.platform.application.dto.admin_settings_dto.mail import MailTemplateKindResult
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailTemplate
from src.modules.platform.domain.services.mail_template_specs import MAIL_TEMPLATE_SPECS
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind


class MailSettingsMapper:
    @staticmethod
    def mail_to_result(e: AdminMailSettings) -> AdminMailSettingsResult:
        return AdminMailSettingsResult(
            id=e.id,
            public_id=e.public_id,
            enabled=e.enabled,
            host=e.host,
            port=e.port,
            user=e.user,
            password_configured=e.password is not None and e.password != "",
            from_address=e.from_address,
            use_tls=e.use_tls,
            use_ssl=e.use_ssl,
            verify_certificate=e.verify_certificate,
            from_display_name=e.from_display_name,
            reply_to=e.reply_to,
            send_limit_per_hour=e.send_limit_per_hour,
            send_lock_minutes=e.send_lock_minutes,
            alert_recipients=list(e.alert_recipients),
            attachment_limit_mb=e.attachment_limit_mb,
        )

    @staticmethod
    def mail_template_to_result(e: AdminMailTemplate) -> AdminMailTemplateResult:
        return AdminMailTemplateResult(
            id=e.id,
            public_id=e.public_id,
            kind=e.kind,
            language=e.language,
            subject=e.subject,
            body=e.body,
            # Defined once here: a blank body means "not translated", and both the status chip
            # and the mail-service fallback read this flag rather than deriving it.
            configured=bool(e.body.strip()),
        )

    @staticmethod
    def mail_template_kind_to_result(
        kind: MailTemplateKind, rows: list[AdminMailTemplate]
    ) -> MailTemplateKindResult:
        spec = MAIL_TEMPLATE_SPECS[kind]
        return MailTemplateKindResult(
            kind=kind,
            family=spec.family,
            variables=spec.variables,
            default_subject=spec.default_subject,
            entries=[MailSettingsMapper.mail_template_to_result(r) for r in rows if r.kind == kind],
        )

    @staticmethod
    def mail_templates_to_result(rows: list[AdminMailTemplate]) -> AdminMailTemplatesResult:
        by_kind: dict[MailTemplateKind, list[AdminMailTemplate]] = {}
        for row in rows:
            by_kind.setdefault(row.kind, []).append(row)
        return AdminMailTemplatesResult(
            kinds=[
                MailSettingsMapper.mail_template_kind_to_result(kind, by_kind.get(kind, []))
                for kind in MAIL_TEMPLATE_SPECS
            ]
        )
