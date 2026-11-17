"""
ORM model for Sequence. The steps and the names frozen at release are JSON;
their shape is the stored form of sequence_content.py. The document
control constraints live on the model so
`Base.metadata.create_all` gives the integration tests the same rules
Postgres gets.

The product key restricts rather than cascades: removing a product must
never take its released revisions with it.
"""

from typing import TYPE_CHECKING
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.quality.adapters.outbound.persistence.models.controlled_document_columns import (
    ControlledDocumentColumns,
)
from src.modules.quality.adapters.outbound.persistence.models.controlled_document_columns import (
    controlled_document_table_args,
)

if TYPE_CHECKING:
    from src.modules.workspace.adapters.outbound.persistence.models.product_model import (
        ProductOrmModel,
    )


class SequenceOrmModel(ControlledDocumentColumns, Base):
    __tablename__ = "sequence_table"

    __table_args__ = (*controlled_document_table_args("sequence"),)

    CONSTRAINT_PREFIX = "sequence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_table.id", name="fk_sequence_product_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product: Mapped["ProductOrmModel"] = relationship(
        "src.modules.workspace.adapters.outbound.persistence.models.product_model.ProductOrmModel",
        foreign_keys=[product_id],
        lazy="raise_on_sql",
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    frozen: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
