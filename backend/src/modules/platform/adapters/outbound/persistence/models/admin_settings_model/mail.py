"""
ORM models for outbound mail: the admin_mail_settings singleton and the
admin_mail_template rows, one per (kind, language).
"""

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.encrypted_type import EncryptedString
from src.modules.platform.adapters.outbound.persistence.models.base import Base


class AdminMailSettingsOrmModel(Base):
    __tablename__ = "admin_mail_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    host: Mapped[str] = mapped_column(String, nullable=False, server_default="localhost")
    port: Mapped[int] = mapped_column(Integer, nullable=False, server_default="587")
    user: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    # Encrypted at rest with SECURITY__ENCRYPTION_KEY, see encrypted_type.py.
    # Never returned by the API, see admin_settings_mapper's
    # password_configured flag.
    password: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    from_address: Mapped[str | None] = mapped_column(String, nullable=True)
    use_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    use_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # Verifies the SMTP server's certificate unless an admin turns it off,
    # for a relay that presents a certificate from an internal CA.
    verify_certificate: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # "" = no display name, the bare address is sent. See
    # AdminMailSettings.from_display_name.
    from_display_name: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    reply_to: Mapped[str | None] = mapped_column(String, nullable=True)
    # Per-user send-mail rate limit, see domain/services/mail_policy.py.
    send_limit_per_hour: Mapped[int] = mapped_column(Integer, nullable=False, server_default="20")
    send_lock_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="60")
    # Ops-alert recipients for the schedule-error/disk-space-warning
    # mails. Same JSON-list shape as AdminMaintenanceSettingsOrmModel.
    # allowed_ips (maintenance.py).
    alert_recipients: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    # The total size, in megabytes, the attachments of one composed mail
    # may have.
    attachment_limit_mb: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")


class AdminMailTemplateOrmModel(Base):
    """One localized, admin-editable mail template row. Surrogate
    autoincrement `id` PK (Entity.id is an int and Base.public_id needs
    per-row identity, so this is not a composite (kind, language) PK),
    plus a UNIQUE(kind, language) constraint: a kind has at most one row
    per language. Unlike every other table in this package, this one is
    not a singleton: it holds one row per (kind, language) pair an admin
    saved or imported, and a pair without a row falls back to the packaged
    file (see mail_template_resolution.py).
    """

    __tablename__ = "admin_mail_template"
    __table_args__ = (
        UniqueConstraint("kind", "language", name="uq_admin_mail_template_kind_language"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    # Text, not String: bodies are multi-KB HTML documents.
    body: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
