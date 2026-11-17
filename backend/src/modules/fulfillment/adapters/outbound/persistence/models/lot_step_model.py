"""
SQLAlchemy ORM model for lot_step_table: one ordered step within a lot
position, either a fabrication step tied to a FabricationMethod or an
inspection step tied to an InspectionMethod, enforced by the role check
constraints below. source_process optionally links back to the made
item's process the step was seeded from. Infrastructure detail, never
imported by domain or application layers.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.platform.adapters.outbound.persistence.models.base import Base

if TYPE_CHECKING:
    from src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model import (
        FabricationMethodOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.inspection_method_model import (
        InspectionMethodOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.made_item_process_model import (
        MadeItemProcessOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
        LotPositionOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class LotStepOrmModel(Base):
    __tablename__ = "lot_step_table"
    __table_args__ = (
        UniqueConstraint("lot_id", "sequence", name="uq_lot_step_lot_id_sequence"),
        CheckConstraint(
            "(role = 'fabrication' AND fabrication_method_id IS NOT NULL) OR "
            "(role = 'inspection' AND fabrication_method_id IS NULL)",
            name="ck_lot_step_role_method",
        ),
        CheckConstraint(
            "(role = 'inspection' AND inspection_method_id IS NOT NULL) OR "
            "(role = 'fabrication' AND inspection_method_id IS NULL)",
            name="ck_lot_step_inspection_method",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    note: Mapped[str | None] = mapped_column(String, nullable=True)
    estimated_setup_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_minutes_per_piece: Mapped[float | None] = mapped_column(Float, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    time_budget_per_piece: Mapped[float | None] = mapped_column(Float, nullable=True)

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_lot_step_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    fabrication_method_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("fabrication_method_table.id", name="fk_lot_step_fabrication_method_id"),
        nullable=True,
        index=True,
    )
    fabrication_method: Mapped["FabricationMethodOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model.FabricationMethodOrmModel",
        foreign_keys=[fabrication_method_id],
        lazy="raise_on_sql",
    )

    role: Mapped[str] = mapped_column(String, nullable=False, default=StepRole.default().value)

    inspection_method_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("inspection_method_table.id", name="fk_lot_step_inspection_method_id"),
        nullable=True,
        index=True,
    )
    inspection_method: Mapped["InspectionMethodOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.inspection_method_model.InspectionMethodOrmModel",
        foreign_keys=[inspection_method_id],
        lazy="raise_on_sql",
    )

    lot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("production_lot_table.id", name="fk_lot_step_lot_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    position_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("lot_position_table.id", name="fk_lot_step_position_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped["LotPositionOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model.LotPositionOrmModel",
        back_populates="steps",
        foreign_keys=[position_id],
        lazy="raise_on_sql",
    )

    source_process_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "made_item_process_table.id",
            name="fk_lot_step_source_process_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    source_process: Mapped["MadeItemProcessOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.made_item_process_model.MadeItemProcessOrmModel",
        foreign_keys=[source_process_id],
        lazy="raise_on_sql",
    )
