"""
SQLAlchemy ORM model for messages to terminals and the two link tables of
their pick audience. Infrastructure detail, never imported by domain or
application layers.

A message to every terminal has no link rows. A pick lists its terminals and
its infoscreens in the link tables; deleting a terminal or a screen removes
its link rows on Postgres through the cascade, and the rules ignore an id
that no longer exists anyway.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import false

from src.modules.platform.adapters.outbound.persistence.models.base import Base

if TYPE_CHECKING:
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


terminal_broadcast_terminal_table = sa.Table(
    "terminal_broadcast_terminal_table",
    Base.metadata,
    sa.Column(
        "broadcast_id",
        Integer,
        ForeignKey(
            "terminal_broadcast_table.id",
            name="fk_terminal_broadcast_terminal_broadcast_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
    sa.Column(
        "terminal_id",
        Integer,
        ForeignKey(
            "terminal_table.id",
            name="fk_terminal_broadcast_terminal_terminal_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
        index=True,
    ),
)

terminal_broadcast_infoscreen_table = sa.Table(
    "terminal_broadcast_infoscreen_table",
    Base.metadata,
    sa.Column(
        "broadcast_id",
        Integer,
        ForeignKey(
            "terminal_broadcast_table.id",
            name="fk_terminal_broadcast_infoscreen_broadcast_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
    sa.Column(
        "infoscreen_id",
        Integer,
        ForeignKey(
            "infoscreen_table.id",
            name="fk_terminal_broadcast_infoscreen_infoscreen_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
        index=True,
    ),
)


class TerminalBroadcastOrmModel(Base):
    __tablename__ = "terminal_broadcast_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    text: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    style: Mapped[str] = mapped_column(String, nullable=False)
    show_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    all_terminals: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_terminal_broadcast_created_by_id"),
        nullable=False,
        index=True,
    )
    created_by: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[created_by_id],
        lazy="raise_on_sql",
    )
