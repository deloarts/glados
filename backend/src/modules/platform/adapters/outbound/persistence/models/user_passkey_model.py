"""
SQLAlchemy ORM model for passkeys (WebAuthn credentials). Only the public
key is stored, the private key never leaves the authenticator.
Infrastructure detail, never imported by domain or application layers.
"""

from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import LargeBinary
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class UserPasskeyOrmModel(Base):
    __tablename__ = "user_passkey_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "user_table.id",
            name="fk_user_passkey_table_user_id_user_table",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )
    # Unique across all users: a login looks the credential up by this ID
    # alone, before it knows whose it is.
    credential_id: Mapped[bytes] = mapped_column(
        LargeBinary, unique=True, index=True, nullable=False
    )
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    name: Mapped[str] = mapped_column(String, nullable=False)
    transports: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    backed_up: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
