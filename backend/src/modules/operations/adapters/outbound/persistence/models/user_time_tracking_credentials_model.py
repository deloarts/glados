"""
One row per Glados user who stored time tracking credentials, see
UserTimeTrackingCredentials' docstring. The user name is an EncryptedString
column, encrypted at rest with SECURITY__ENCRYPTION_KEY and re-encrypted on
key rotation by reencrypt_stored_secrets; the password exists only inside
the sealed value, which only the time tracking service can open. The row is
removed with its user (ON DELETE CASCADE).

Server defaults exist only where a neutral value is safe: an empty binding
or key id and consent version 0 all read as "must be confirmed again"
rather than as valid state.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import func
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.encrypted_type import EncryptedString
from src.modules.platform.adapters.outbound.persistence.models.base import Base


class UserTimeTrackingCredentialsOrmModel(Base):
    __tablename__ = "user_time_tracking_credentials"

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_time_tracking_credentials_user_id"),
        UniqueConstraint(
            "time_tracking_user_fingerprint",
            name="uq_user_time_tracking_credentials_fingerprint",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "user_table.id",
            name="fk_user_time_tracking_credentials_user_id_user_table",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    time_tracking_user: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    time_tracking_sealed_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_tracking_binding: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=""
    )
    time_tracking_credential_key_id: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=""
    )
    time_tracking_user_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    time_tracking_user_fingerprint_key_id: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default=""
    )
    time_tracking_auth_failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    time_tracking_consent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    time_tracking_consent_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
