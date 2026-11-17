"""
SQLAlchemy ORM model for article groups and their join tables.
Infrastructure detail, never imported by domain or application layers.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import false

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType

if TYPE_CHECKING:
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel

# Many-to-many: a bought item can belong to multiple article groups.
bought_item_article_group_table = sa.Table(
    "bought_item_article_group_table",
    Base.metadata,
    sa.Column(
        "bought_item_id",
        Integer,
        ForeignKey("bought_item_table.id", name="fk_bought_item_article_group_bought_item_id"),
        primary_key=True,
    ),
    sa.Column(
        "article_group_id",
        Integer,
        ForeignKey("article_group_table.id", name="fk_bought_item_article_group_article_group_id"),
        primary_key=True,
        index=True,
    ),
)

# Many-to-many: a made item can belong to multiple article groups.
made_item_article_group_table = sa.Table(
    "made_item_article_group_table",
    Base.metadata,
    sa.Column(
        "made_item_id",
        Integer,
        ForeignKey("made_item_table.id", name="fk_made_item_article_group_made_item_id"),
        primary_key=True,
    ),
    sa.Column(
        "article_group_id",
        Integer,
        ForeignKey("article_group_table.id", name="fk_made_item_article_group_article_group_id"),
        primary_key=True,
        index=True,
    ),
)


class ArticleGroupOrmModel(ChangedByColumns, Base):
    __tablename__ = "article_group_table"

    # `name` uniqueness is scoped to non-archived rows, the same partial
    # unique index pattern customer/supplier/product use. A plain UNIQUE column would
    # keep an archived row's name reserved forever.

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
    # Position in the hand-kept order of the list, see the entity.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # ── Core fields ───────────────────────────────────────────────────
    # Text per language code (LocalizedText). Names are unique per language
    # among live rows, enforced by the use cases (label_name_rules.py).
    name: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    label_color: Mapped[str] = mapped_column(String, nullable=False, default="#999999")
    label_font_color: Mapped[str] = mapped_column(
        String, nullable=False, default="#000000", server_default="#000000"
    )
    description: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)

    # ── Audit ─────────────────────────────────────────────────────────
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_article_group_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )
