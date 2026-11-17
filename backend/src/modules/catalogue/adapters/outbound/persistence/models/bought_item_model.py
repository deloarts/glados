"""
Catalogue record ORM model. No config imports.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import false
from sqlalchemy.sql import text

from src.modules.catalogue.adapters.outbound.persistence.models.article_group_model import (
    bought_item_article_group_table,
)
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType
from src.modules.platform.adapters.outbound.persistence.models.edit_version_column import (
    EditVersionColumn,
)
from src.modules.platform.adapters.outbound.persistence.models.percent_type import PercentType

if TYPE_CHECKING:
    from src.modules.catalogue.adapters.outbound.persistence.models.article_group_model import (
        ArticleGroupOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_file_model import (
        BoughtItemFileOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.product_family_model import (
        ProductFamilyOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
        SupplierOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class BoughtItemOrmModel(EditVersionColumn, ChangedByColumns, Base):
    __tablename__ = "bought_item_table"
    # Sync bookkeeping no form edits leaves the edit version alone.
    __edit_version_ignored__ = frozenset(
        {"pdm_file_version", "pdm_synced_at", "pdm_sync_state", "edp_synced_at"}
    )

    # gtin uniqueness is scoped to non-archived rows by a partial unique
    # index, because a plain UNIQUE column would keep an archived item's GTIN reserved
    # forever, so the application-level pre-check in create/update_bought_item
    # (which reads only live rows) would pass while the INSERT/UPDATE still
    # 500s. `ix_bought_item_trgm_search` (GIN trigram search index) is a
    # hand-maintained raw-SQL expression index, not declared here, see
    # env.py's `include_object` hook, which excludes it from comparison by
    # name rather than risk a byte-for-byte expression mismatch against
    # Postgres's normalised rendering.
    # `part_number` uniqueness is TOTAL, archived rows included, unlike
    # gtin above, because a number is only ever freed by
    # part_number_registry.release_if_unused (a hard delete). Partial only
    # on `part_number IS NOT NULL`: a row may be part_number=None before
    # PDM assigns or claims one.
    __table_args__ = (
        Index(
            "uq_bought_item_gtin_active",
            "gtin",
            unique=True,
            postgresql_where=text("archived IS false"),
            sqlite_where=text("archived = 0"),
        ),
        Index(
            "uq_bought_item_part_number",
            "part_number",
            unique=True,
            postgresql_where=text("part_number IS NOT NULL"),
            sqlite_where=text("part_number IS NOT NULL"),
        ),
        # Identity per docs/reference/field-ownership.md section 1.2: one row
        # per PDM file, (vault_id, pdm_file_id). Partial on `pdm_file_id IS NOT NULL`: a
        # WEB row has no PDM file until claimed.
        Index(
            "uq_bought_item_pdm_file",
            "vault_id",
            "pdm_file_id",
            unique=True,
            postgresql_where=text("pdm_file_id IS NOT NULL"),
            sqlite_where=text("pdm_file_id IS NOT NULL"),
        ),
    )

    # ── Server-managed ────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    # ── External core fields ──────────────────────────────────────────
    order_code_1: Mapped[str] = mapped_column(String, nullable=False, index=True)
    order_code_2: Mapped[str | None] = mapped_column(String, nullable=True)
    gtin: Mapped[str | None] = mapped_column(String, nullable=True)
    ean: Mapped[str | None] = mapped_column(String, nullable=True)
    tariff_number: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Internal core fields ──────────────────────────────────────────
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    article_name: Mapped[str] = mapped_column(String, nullable=False)
    data_source: Mapped[str] = mapped_column(String, nullable=False, default="WEB")
    part_number: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    # Latest released PDM revision of the file, `null` on WEB rows.
    # Read-only passthrough: no create/update use case writes this yet,
    # only PDM ingest is meant to.
    revision: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Internal additional fields ────────────────────────────────────
    mass: Mapped[int | None] = mapped_column(Integer, nullable=True)  # in grams
    successor_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("bought_item_table.id", name="fk_bought_item_successor_id"),
        nullable=True,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    weblink: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── PDM link ─────────────────────────────────────────────────────
    vault_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pdm_file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pdm_file_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pdm_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pdm_sync_state: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── Relations ─────────────────────────────────────────────────────
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_bought_item_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    approver_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_bought_item_approver_id"),
        nullable=True,
        index=True,
    )
    approver: Mapped["UserOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[approver_id],
        lazy="raise_on_sql",
    )

    manufacturer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("supplier_table.id", name="fk_bought_item_manufacturer_id"),
        nullable=False,
        index=True,
    )
    manufacturer: Mapped["SupplierOrmModel"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.supplier_model.SupplierOrmModel",
        foreign_keys=[manufacturer_id],
        lazy="raise_on_sql",
    )

    product_family_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("product_family_table.id", name="fk_bought_item_product_family_id"),
        nullable=True,
        index=True,
    )
    product_family: Mapped["ProductFamilyOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.product_family_model.ProductFamilyOrmModel",
        foreign_keys=[product_family_id],
        lazy="raise_on_sql",
    )

    edp_part_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    edp_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pdm_edp_part_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The item's own delivery tolerances in percent, replacing the ones of
    # the order settings; None takes those.
    over_delivery_tolerance_percent: Mapped[float | None] = mapped_column(
        PercentType, nullable=True
    )
    under_delivery_tolerance_percent: Mapped[float | None] = mapped_column(
        PercentType, nullable=True
    )

    article_groups: Mapped[list["ArticleGroupOrmModel"]] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.article_group_model.ArticleGroupOrmModel",
        secondary=bought_item_article_group_table,
        order_by="ArticleGroupOrmModel.id",
        lazy="raise_on_sql",
    )

    files: Mapped[list["BoughtItemFileOrmModel"]] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.bought_item_file_model.BoughtItemFileOrmModel",
        back_populates="bought_item",
        lazy="raise_on_sql",
    )
