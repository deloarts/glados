"""
SQLAlchemy ORM models of the contact links of products and projects. No
config imports. No domain imports.
"""

from datetime import datetime

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.sql import true

from src.modules.platform.adapters.outbound.persistence.models.base import Base


class ProductContactOrmModel(Base):
    """A contact linked to a product, inherited by every project of the
    product."""

    __tablename__ = "product_contact_table"
    __table_args__ = (
        UniqueConstraint("product_id", "contact_id", name="uq_product_contact_product_contact"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_table.id", name="fk_product_contact_product_id", ondelete="CASCADE"),
        nullable=False,
    )
    contact_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("contact_table.id", name="fk_product_contact_contact_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    receives_meeting_notes: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_product_contact_creator_id"),
        nullable=False,
        index=True,
    )


class ProjectContactOrmModel(Base):
    """A contact linked to a project. A row for a contact the project's
    product links too overrides the product's meeting notes flag for this
    project, which is how a project mutes an inherited contact."""

    __tablename__ = "project_contact_table"
    __table_args__ = (
        UniqueConstraint("project_id", "contact_id", name="uq_project_contact_project_contact"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("project_table.id", name="fk_project_contact_project_id", ondelete="CASCADE"),
        nullable=False,
    )
    contact_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("contact_table.id", name="fk_project_contact_contact_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    receives_meeting_notes: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_project_contact_creator_id"),
        nullable=False,
        index=True,
    )
