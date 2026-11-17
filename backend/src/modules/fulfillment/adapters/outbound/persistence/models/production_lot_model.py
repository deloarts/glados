"""
ORM model for production_lot_table, a batch-production run of a made item for a project.
Tracks status, quantity and scrap totals, the material source (bought, source, or made
item), QA/rework lineage, and the source-item approval workflow, and owns the lot's ordered
positions.
"""

from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType
from src.modules.platform.adapters.outbound.persistence.models.quantity_type import QuantityType

if TYPE_CHECKING:
    from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
        BoughtItemOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
        MadeItemOrmModel,
    )
    from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
        SourceItemOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
        LotPositionOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
        SourceItemDemandItemOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
    from src.modules.workspace.adapters.outbound.persistence.models.project_model import (
        ProjectOrmModel,
    )


class ProductionLotOrmModel(ChangedByColumns, Base):
    __tablename__ = "production_lot_table"
    __table_args__ = (
        CheckConstraint(
            "(origin_lot_id IS NULL AND origin_disposition IS NULL) OR "
            "(origin_lot_id IS NOT NULL AND origin_disposition IS NOT NULL)",
            name="ck_production_lot_origin",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    lot_number: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    quantity: Mapped[float] = mapped_column(QuantityType, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=LotStatus.default().value, index=True
    )
    priority: Mapped[str] = mapped_column(
        String, nullable=False, default=UrgencyClass.default().value
    )
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    required_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Stamped when the lot reaches COMPLETED (forced or automatic), cleared
    # by ResumeLot. See production_lot.py's matching field docstring.
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Running total of pieces scrapped against this lot. See
    # production_lot.py's matching field docstring.
    quantity_scrapped: Mapped[float] = mapped_column(
        QuantityType, nullable=False, default=0.0, server_default="0"
    )

    # Lifecycle intents, see production_lot.py's matching field comment.
    held_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    force_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Row version for optimistic concurrency control: the mapper's version
    # column, so every ORM update and delete checks the version it read and
    # increments it. A writer whose copy is older than the row gets
    # StaleDataError, which the API answers with 409.
    # Moves on every user edit and irreversible action only, never on a
    # derived status or a planned date, so a client can send the value it
    # read and learn of a concurrent edit (expected_edit_version).
    edit_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012 - read once by the mapper

    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_production_lot_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    made_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("made_item_table.id", name="fk_production_lot_made_item_id"),
        nullable=False,
        index=True,
    )
    made_item: Mapped["MadeItemOrmModel"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.made_item_model.MadeItemOrmModel",
        foreign_keys=[made_item_id],
        lazy="raise_on_sql",
    )

    # ── Material source (seeded from the made item at creation, switchable
    # per lot afterward), exactly one of the three is set, or none. ───────
    source_bought_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("bought_item_table.id", name="fk_production_lot_source_bought_item_id"),
        nullable=True,
        index=True,
    )
    source_bought_item: Mapped["BoughtItemOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model.BoughtItemOrmModel",
        foreign_keys=[source_bought_item_id],
        lazy="raise_on_sql",
    )

    source_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("source_item_table.id", name="fk_production_lot_source_item_id"),
        nullable=True,
        index=True,
    )
    source_item: Mapped["SourceItemOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.source_item_model.SourceItemOrmModel",
        foreign_keys=[source_item_id],
        lazy="raise_on_sql",
    )

    # Rework/alteration case, this lot's input is drawn from an existing
    # made item rather than purchased/spec'd raw material.
    source_made_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("made_item_table.id", name="fk_production_lot_source_made_item_id"),
        nullable=True,
        index=True,
    )
    source_made_item: Mapped["MadeItemOrmModel | None"] = relationship(
        "src.modules.catalogue.adapters.outbound.persistence.models.made_item_model.MadeItemOrmModel",
        foreign_keys=[source_made_item_id],
        lazy="raise_on_sql",
    )

    # QA/inspection lineage. See ProductionLot.origin_lot_id's own
    # docstring. Self-referential FK, no ORM relationship object (the
    # repo mapper resolves origin_lot_number/follow_up_lots with plain
    # queries instead, same precedent as source_order_*).
    origin_lot_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("production_lot_table.id", name="fk_production_lot_origin_lot_id"),
        nullable=True,
        index=True,
    )
    origin_disposition: Mapped[str | None] = mapped_column(String, nullable=True)

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("project_table.id", name="fk_production_lot_project_id"),
        nullable=False,
        index=True,
    )
    project: Mapped["ProjectOrmModel"] = relationship(
        "src.modules.workspace.adapters.outbound.persistence.models.project_model.ProjectOrmModel",
        foreign_keys=[project_id],
        lazy="raise_on_sql",
    )

    # Circular FK, intentional: production_lot_table -> source_item_demand_
    # item_table (here) and source_item_demand_item_table.lot_id ->
    # production_lot_table (source_item_demand_item_model.py) form a cycle.
    # This column is nullable (a lot doesn't need an input demand), so
    # insert order is only constrained one way: a demand row cannot
    # precede its lot, since the demand side is NOT NULL. Do not add
    # `use_alter=True`: it changes nothing at runtime, because both tables
    # exist before any row is written, while adding an ALTER-emitting code
    # path.
    # SQLAlchemy currently only warns
    # (`Cannot correctly sort tables ... unresolvable cycles`) when
    # touching Base.metadata.sorted_tables; revisit before any major
    # SQLAlchemy upgrade that turns the warning into an error.
    input_demand_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("source_item_demand_item_table.id", name="fk_production_lot_input_demand_id"),
        nullable=True,
        index=True,
    )
    input_demand: Mapped["SourceItemDemandItemOrmModel | None"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model.SourceItemDemandItemOrmModel",
        foreign_keys=[input_demand_id],
        lazy="raise_on_sql",
    )

    # ── Source item approval (see source_approval_status.py). A stored
    # column, not derived, so the
    # "Needs Approval" list filter has a cheap SQL predicate, the same call
    # `status` above already makes, hence the matching index=True. Exactly
    # one of the two decision pairs is ever set at a time, enforced by
    # ApproveLotSource/RejectLotSource rather than by a DB constraint (mirrors
    # ck_production_lot_origin's precedent of leaving cross-column
    # invariants to the use case layer). ─────────────────────────────────
    source_approval_status: Mapped[str] = mapped_column(
        String, nullable=False, default="not_required", server_default="not_required", index=True
    )
    source_approved_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_production_lot_source_approved_by_id"),
        nullable=True,
        index=True,
    )
    source_approved_by: Mapped["UserOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[source_approved_by_id],
        lazy="raise_on_sql",
    )
    source_approved_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_rejected_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_production_lot_source_rejected_by_id"),
        nullable=True,
        index=True,
    )
    source_rejected_by: Mapped["UserOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[source_rejected_by_id],
        lazy="raise_on_sql",
    )
    source_rejected_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    positions: Mapped[list["LotPositionOrmModel"]] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model.LotPositionOrmModel",
        back_populates="lot",
        order_by="LotPositionOrmModel.sequence",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )
