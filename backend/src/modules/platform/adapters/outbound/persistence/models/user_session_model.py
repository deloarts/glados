"""
SQLAlchemy ORM model for server-side sessions. The JWT's `sid` claim is
this row's public_id (inherited from Base), there is no token hash here;
possession of a validly-signed JWT naming a live row is the credential.
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


class UserSessionOrmModel(Base):
    __tablename__ = "user_session_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "user_table.id",
            name="fk_user_session_table_user_id_user_table",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
    ip: Mapped[str | None] = mapped_column(String, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
