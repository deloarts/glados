"""
ORM model for Calculation. The single-owner check and the document control
constraints live on the model so
`Base.metadata.create_all` gives the integration tests the same rules
Postgres gets.
The owner keys restrict rather than cascade: removing a project or product
must never take its released revisions with it.
"""

from typing import TYPE_CHECKING
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import CheckConstraint
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
    from src.modules.workspace.adapters.outbound.persistence.models.product_device_model import (
        ProductDeviceOrmModel,
    )
    from src.modules.workspace.adapters.outbound.persistence.models.product_model import (
        ProductOrmModel,
    )
    from src.modules.workspace.adapters.outbound.persistence.models.project_model import (
        ProjectOrmModel,
    )


class CalculationOrmModel(ControlledDocumentColumns, Base):
    __tablename__ = "calculation_table"
    __table_args__ = (
        CheckConstraint(
            "project_id IS NULL OR product_id IS NULL", name="ck_calculation_single_owner"
        ),
        *controlled_document_table_args("calculation"),
    )
    CONSTRAINT_PREFIX = "calculation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)

    tool: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    results: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    input_version: Mapped[int] = mapped_column(Integer, nullable=False)
    engine_version: Mapped[int] = mapped_column(Integer, nullable=False)

    project_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("project_table.id", name="fk_calculation_project_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    project: Mapped["ProjectOrmModel | None"] = relationship(
        "src.modules.workspace.adapters.outbound.persistence.models.project_model.ProjectOrmModel",
        foreign_keys=[project_id],
        lazy="raise_on_sql",
    )

    product_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("product_table.id", name="fk_calculation_product_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    product: Mapped["ProductOrmModel | None"] = relationship(
        "src.modules.workspace.adapters.outbound.persistence.models.product_model.ProductOrmModel",
        foreign_keys=[product_id],
        lazy="raise_on_sql",
    )

    # Devices are archived, never deleted, so the reference always resolves.
    product_device_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("product_device_table.id", name="fk_calculation_product_device_id"),
        nullable=True,
        index=True,
    )
    product_device: Mapped["ProductDeviceOrmModel | None"] = relationship(
        "src.modules.workspace.adapters.outbound.persistence.models.product_device_model.ProductDeviceOrmModel",
        foreign_keys=[product_device_id],
        lazy="raise_on_sql",
    )
    # The device name with product number frozen at release.
    product_device_name: Mapped[str | None] = mapped_column(String, nullable=True)
