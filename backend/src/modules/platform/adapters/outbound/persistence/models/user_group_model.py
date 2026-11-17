"""
ORM model for user groups, named bundles of permissions, and the membership
table that links them to users. No config imports.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy import text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType

if TYPE_CHECKING:
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel

# Many-to-many between groups and users. Deleting either side removes the
# membership, so a deleted group or user leaves no dangling rows.
user_group_member_table = sa.Table(
    "user_group_member_table",
    Base.metadata,
    sa.Column(
        "group_id",
        Integer,
        ForeignKey("user_group_table.id", name="fk_user_group_member_group_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "user_id",
        Integer,
        ForeignKey("user_table.id", name="fk_user_group_member_user_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)


class UserGroupOrmModel(ChangedByColumns, Base):
    __tablename__ = "user_group_table"
    __table_args__ = (Index("uq_user_group_name_ci", func.lower(text("name")), unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    permissions: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_user_group_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )
    members: Mapped[list["UserOrmModel"]] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        secondary=user_group_member_table,
        back_populates="groups",
        # The membership table cascades on delete, so removing a row never
        # needs this collection loaded.
        passive_deletes=True,
        lazy="raise_on_sql",
    )
