"""
Catalogue record ORM model. No config imports.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import false
from sqlalchemy.sql import true

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType

if TYPE_CHECKING:
    from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
        BoughtItemOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel

# Many-to-many: a printer may consume several stocked items (labels, ribbon,
# toner), kept for quick reordering, not for stock deduction.
printer_bought_item_table = sa.Table(
    "printer_bought_item_table",
    Base.metadata,
    sa.Column(
        "printer_id",
        Integer,
        ForeignKey(
            "printer_table.id", name="fk_printer_bought_item_printer_id", ondelete="CASCADE"
        ),
        primary_key=True,
    ),
    sa.Column(
        "bought_item_id",
        Integer,
        ForeignKey("bought_item_table.id", name="fk_printer_bought_item_bought_item_id"),
        primary_key=True,
        index=True,
    ),
)


class PrinterOrmModel(ChangedByColumns, Base):
    __tablename__ = "printer_table"

    # ── Server-managed ────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    # ── Core fields ───────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    internal_name: Mapped[str | None] = mapped_column(String, nullable=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)

    # ── Connection ────────────────────────────────────────────────────
    host: Mapped[str] = mapped_column(String, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    timeout_seconds: Mapped[float] = mapped_column(
        Float, nullable=False, default=5.0, server_default="5"
    )
    transport: Mapped[str] = mapped_column(String, nullable=False)
    ipp_uri_path: Mapped[str] = mapped_column(
        String, nullable=False, default="/", server_default="/"
    )

    # ── ZPL specifics ─────────────────────────────────────────────────
    head_dpi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    format_convert_factor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── IPP specifics ─────────────────────────────────────────────────
    default_media: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Descriptive ───────────────────────────────────────────────────
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    vendor: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    firmware: Mapped[str | None] = mapped_column(String, nullable=True)

    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    note: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Relations ─────────────────────────────────────────────────────
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_printer_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    bought_items: Mapped[list["BoughtItemOrmModel"]] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model.BoughtItemOrmModel",
        secondary=printer_bought_item_table,
        order_by="BoughtItemOrmModel.id",
        lazy="raise_on_sql",
    )
