"""
SQLAlchemy ORM model for trusted devices (TOTP "don't ask again"). Only
the SHA-256 hash of the cookie secret is stored, same posture as PATs.
Infrastructure detail, never imported by domain or application layers.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class UserTrustedDeviceOrmModel(Base):
    __tablename__ = "user_trusted_device_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "user_table.id",
            name="fk_user_trusted_device_table_user_id_user_table",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
