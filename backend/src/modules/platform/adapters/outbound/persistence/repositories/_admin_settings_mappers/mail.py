"""
Row mapping for the admin_mail_settings singleton and the admin_mail_template
rows. Converts the ORM row to the domain entity and the entity to the column
dict SqlAlchemyAdminSettingsRepository upserts.
"""

from typing import Any

from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.mail import (
    AdminMailSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.mail import (
    AdminMailTemplateOrmModel,
)
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailTemplate
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind


def to_entity(o: AdminMailSettingsOrmModel) -> AdminMailSettings:
    return AdminMailSettings(
        id=o.id,
        public_id=o.public_id,
        enabled=o.enabled,
        host=o.host,
        port=o.port,
        user=o.user,
        password=o.password,
        from_address=o.from_address,
        use_tls=o.use_tls,
        use_ssl=o.use_ssl,
        verify_certificate=o.verify_certificate,
        from_display_name=o.from_display_name,
        reply_to=o.reply_to,
        send_limit_per_hour=o.send_limit_per_hour,
        send_lock_minutes=o.send_lock_minutes,
        alert_recipients=list(o.alert_recipients or []),
        attachment_limit_mb=o.attachment_limit_mb,
    )


def template_to_entity(o: AdminMailTemplateOrmModel) -> AdminMailTemplate:
    return AdminMailTemplate(
        id=o.id,
        public_id=o.public_id,
        kind=MailTemplateKind(o.kind),
        language=Language(o.language),
        subject=o.subject,
        body=o.body,
    )


def to_dict(s: AdminMailSettings) -> dict[str, Any]:
    return {
        "enabled": s.enabled,
        "host": s.host,
        "port": s.port,
        "user": s.user,
        "password": s.password,
        "from_address": s.from_address,
        "use_tls": s.use_tls,
        "use_ssl": s.use_ssl,
        "verify_certificate": s.verify_certificate,
        "from_display_name": s.from_display_name,
        "reply_to": s.reply_to,
        "send_limit_per_hour": s.send_limit_per_hour,
        "send_lock_minutes": s.send_lock_minutes,
        "alert_recipients": list(s.alert_recipients),
        "attachment_limit_mb": s.attachment_limit_mb,
    }
