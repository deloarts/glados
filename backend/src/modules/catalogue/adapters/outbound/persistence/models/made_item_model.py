"""
Catalogue record ORM model. No config imports.
"""

from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import Date
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
    made_item_article_group_table,
)
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType
from src.modules.platform.adapters.outbound.persistence.models.edit_version_column import (
    EditVersionColumn,
)

if TYPE_CHECKING:
    from src.modules.catalogue.adapters.outbound.persistence.models.article_group_model import (
        ArticleGroupOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
        BoughtItemOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.customer_model import (
        CustomerOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.made_item_file_model import (
        MadeItemFileOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.made_item_process_model import (
        MadeItemProcessOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
        SourceItemOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class MadeItemOrmModel(EditVersionColumn, Base):
    __tablename__ = "made_item_table"
    # Sync bookkeeping no form edits leaves the edit version alone.
    __edit_version_ignored__ = frozenset({"pdm_file_version", "pdm_synced_at", "pdm_sync_state"})

    # (part_number, revision) is
    # unique for made items, TOTAL, archived rows included, unlike
    # the `uq_*_active` partial indexes elsewhere in this file's siblings.
    # A number is only ever freed by part_number_registry.release_if_unused
    # (a hard delete), never by a soft delete. Partial only on
    # `part_number IS NOT NULL`: an external/PDM row may still be
    # part_number=None before it is matched. Declared on the model so every
    # schema built from it, the integration suite's Base.metadata.create_all
    # included, enforces it, like uq_bought_item_gtin_active below.
    # uq_made_item_pdm_file_revision backs identity per docs/reference/field-ownership.md
    # section 1.2: (vault_id, pdm_file_id, revision) is the same key
    # as (part_number, revision) above, addressed by PDM file id instead of the
    # label. Partial on `pdm_file_id IS NOT NULL`: a WEB row has no PDM file yet.
    __table_args__ = (
        Index(
            "uq_made_item_part_number_revision",
            "part_number",
            "revision",
            unique=True,
            postgresql_where=text("part_number IS NOT NULL"),
            sqlite_where=text("part_number IS NOT NULL"),
        ),
        Index(
            "uq_made_item_pdm_file_revision",
            "vault_id",
            "pdm_file_id",
            "revision",
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
    revision: Mapped[str] = mapped_column(String, nullable=False)
    revision_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    revision_note: Mapped[str | None] = mapped_column(String, nullable=True)
    article_name: Mapped[str] = mapped_column(String, nullable=False)

    # ── Internal core fields ──────────────────────────────────────────
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    data_source: Mapped[str] = mapped_column(String, nullable=False, default="WEB")
    part_number: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    # ── Internal additional fields ────────────────────────────────────
    material: Mapped[str | None] = mapped_column(String, nullable=True)
    mass: Mapped[int | None] = mapped_column(Integer, nullable=True)  # in grams
    base_size: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    weblink: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_part_number: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_revision: Mapped[str | None] = mapped_column(String, nullable=True)
    successor_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("made_item_table.id", name="fk_made_item_successor_id"),
        nullable=True,
        index=True,
    )

    # ── PDM link ─────────────────────────────────────────────────────
    vault_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pdm_file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pdm_file_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pdm_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pdm_sync_state: Mapped[str | None] = mapped_column(String, nullable=True)
    pdm_source_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Relations ─────────────────────────────────────────────────────
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_made_item_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    changed_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_made_item_changed_by_id"),
        nullable=True,
        index=True,
    )
    changed_by: Mapped["UserOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[changed_by_id],
        lazy="raise_on_sql",
    )

    approver_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_made_item_approver_id"),
        nullable=True,
        index=True,
    )
    approver: Mapped["UserOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[approver_id],
        lazy="raise_on_sql",
    )

    bought_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("bought_item_table.id", name="fk_made_item_bought_item_id"),
        nullable=True,
        index=True,
    )
    bought_item: Mapped["BoughtItemOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model.BoughtItemOrmModel",
        foreign_keys=[bought_item_id],
        lazy="raise_on_sql",
    )

    source_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("source_item_table.id", name="fk_made_item_source_item_id"),
        nullable=True,
        index=True,
    )
    source_item: Mapped["SourceItemOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.source_item_model.SourceItemOrmModel",
        foreign_keys=[source_item_id],
        lazy="raise_on_sql",
    )

    customer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("customer_table.id", name="fk_made_item_customer_id"),
        nullable=True,
        index=True,
    )
    customer: Mapped["CustomerOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.customer_model.CustomerOrmModel",
        foreign_keys=[customer_id],
        lazy="raise_on_sql",
    )

    article_groups: Mapped[list["ArticleGroupOrmModel"]] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.article_group_model.ArticleGroupOrmModel",
        secondary=made_item_article_group_table,
        order_by="ArticleGroupOrmModel.id",
        lazy="raise_on_sql",
    )

    files: Mapped[list["MadeItemFileOrmModel"]] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.made_item_file_model.MadeItemFileOrmModel",
        back_populates="made_item",
        lazy="raise_on_sql",
    )

    processes: Mapped[list["MadeItemProcessOrmModel"]] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.made_item_process_model.MadeItemProcessOrmModel",
        back_populates="made_item",
        order_by="MadeItemProcessOrmModel.position",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )
