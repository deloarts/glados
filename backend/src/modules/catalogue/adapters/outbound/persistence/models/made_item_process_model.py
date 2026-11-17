"""
SQLAlchemy ORM model for made_item_process_table: one ordered process step
in a made item's routing template, either a fabrication step tied to a
FabricationMethod or an inspection step tied to an InspectionMethod, used
to seed a lot's LotSteps at lot creation. Infrastructure detail, never
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
    from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
        MadeItemOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


class MadeItemProcessOrmModel(Base):
    __tablename__ = "made_item_process_table"
    __table_args__ = (
        CheckConstraint(
            "(role = 'fabrication' AND fabrication_method_id IS NOT NULL) OR "
            "(role = 'inspection' AND fabrication_method_id IS NULL)",
            name="ck_made_item_process_role_method",
        ),
        CheckConstraint(
            "(role = 'inspection' AND inspection_method_id IS NOT NULL) OR "
            "(role = 'fabrication' AND inspection_method_id IS NULL)",
            name="ck_made_item_process_inspection_method",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    note: Mapped[str | None] = mapped_column(String, nullable=True)
    estimated_setup_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_minutes_per_piece: Mapped[float | None] = mapped_column(Float, nullable=True)

    made_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "made_item_table.id", name="fk_made_item_process_made_item_id", ondelete="CASCADE"
        ),
        nullable=False,
        index=True,
    )
    made_item: Mapped["MadeItemOrmModel"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.made_item_model.MadeItemOrmModel",
        back_populates="processes",
        lazy="raise_on_sql",
    )

    fabrication_method_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "fabrication_method_table.id", name="fk_made_item_process_fabrication_method_id"
        ),
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
        ForeignKey("inspection_method_table.id", name="fk_made_item_process_inspection_method_id"),
        nullable=True,
        index=True,
    )
    inspection_method: Mapped["InspectionMethodOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.inspection_method_model.InspectionMethodOrmModel",
        foreign_keys=[inspection_method_id],
        lazy="raise_on_sql",
    )

    position: Mapped[int] = mapped_column(Integer, nullable=False)
    group_index: Mapped[int] = mapped_column(Integer, nullable=False)

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_made_item_process_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )
