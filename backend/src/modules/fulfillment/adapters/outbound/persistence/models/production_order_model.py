"""ORM model for production orders, the internal work queued against a lot position (machine
or machine pool assignment, scheduling, actuals, status)."""

from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import CheckConstraint
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import false

from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.changed_by_columns import (
    ChangedByColumns,
)
from src.modules.platform.adapters.outbound.persistence.models.changelog_type import ChangelogType
from src.modules.platform.adapters.outbound.persistence.models.quantity_type import QuantityType

if TYPE_CHECKING:
    from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
        LotPositionOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.machine_pool_model import (
        MachinePoolOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.production_machine_model import (
        ProductionMachineOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_completion_model import (
        ProductionOrderCompletionOrmModel,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_file_model import (
        ProductionOrderFileOrmModel,
    )
    from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel


# The DB-level uniqueness backstop for queue_sequence, scoped to LIVE
# (non-terminal) orders only. Mirrors ProductionOrderStatus's two terminal
# values (COMPLETED and CANCELED, from which the production order intent
# table offers no action) and next_queue_sequence's three mutually exclusive
# scopes exactly (machine / pool-with-no-machine / neither). Declared on the model so the
# SQLite integration suite enforces the same law Postgres does (SQLite
# supports partial unique indexes via sqlite_where).
_LIVE_QUEUE_SEQUENCE = "status <> 'completed' AND status <> 'canceled'"
_MACHINE_QUEUE_SEQUENCE_WHERE = f"machine_id IS NOT NULL AND {_LIVE_QUEUE_SEQUENCE}"
_POOL_QUEUE_SEQUENCE_WHERE = (
    f"machine_id IS NULL AND machine_pool_id IS NOT NULL AND {_LIVE_QUEUE_SEQUENCE}"
)
_UNASSIGNED_QUEUE_SEQUENCE_WHERE = (
    f"machine_id IS NULL AND machine_pool_id IS NULL AND {_LIVE_QUEUE_SEQUENCE}"
)


class ProductionOrderOrmModel(ChangedByColumns, Base):
    __tablename__ = "production_order_table"
    __table_args__ = (
        CheckConstraint(
            "quantity_completed <= quantity",
            name="ck_production_order_quantity_completed_le_quantity",
        ),
        Index(
            "uq_production_order_queue_sequence_machine",
            "machine_id",
            "queue_sequence",
            unique=True,
            postgresql_where=text(_MACHINE_QUEUE_SEQUENCE_WHERE),
            sqlite_where=text(_MACHINE_QUEUE_SEQUENCE_WHERE),
        ),
        Index(
            "uq_production_order_queue_sequence_pool",
            "machine_pool_id",
            "queue_sequence",
            unique=True,
            postgresql_where=text(_POOL_QUEUE_SEQUENCE_WHERE),
            sqlite_where=text(_POOL_QUEUE_SEQUENCE_WHERE),
        ),
        Index(
            "uq_production_order_queue_sequence_unassigned",
            "queue_sequence",
            unique=True,
            postgresql_where=text(_UNASSIGNED_QUEUE_SEQUENCE_WHERE),
            sqlite_where=text(_UNASSIGNED_QUEUE_SEQUENCE_WHERE),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ChangelogType), nullable=False, default=[]
    )

    production_order_number: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=ProductionOrderStatus.default().value, index=True
    )
    priority: Mapped[str] = mapped_column(
        String, nullable=False, default=UrgencyClass.default().value
    )
    pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    queue_sequence: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    quantity: Mapped[float] = mapped_column(QuantityType, nullable=False)
    quantity_completed: Mapped[float] = mapped_column(
        QuantityType, nullable=False, default=0.0, server_default="0"
    )
    estimated_duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    note: Mapped[str | None] = mapped_column(String, nullable=True)

    # Scheduling (set by the scheduler; unset until a schedule is computed)
    planned_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    not_before: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Actuals
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Lifecycle intent, see production_order.py's matching field comment.
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
        ForeignKey("user_table.id", name="fk_production_order_creator_id"),
        nullable=False,
        index=True,
    )
    creator: Mapped["UserOrmModel"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[creator_id],
        lazy="raise_on_sql",
    )

    # Who set the CURRENT planned_start/planned_end: a specific person
    # when manually pinned (UpdateProductionOrder), None when the
    # scheduler auto-computed it (RecomputeMachineSchedule clears this for
    # any non-pinned order it touches). None reads as "Auto-planner" at
    # the API/frontend layer.
    planned_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_production_order_planned_by_id"),
        nullable=True,
        index=True,
    )
    planned_by: Mapped["UserOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[planned_by_id],
        lazy="raise_on_sql",
    )

    # The operator resolved (resolve_operator_id) on the CURRENT/last start,
    # overwritten on every start/resume: it means "who is running this order
    # right now, or who last did." Untouched by pause/complete/cancel. Not a
    # substitute for ProductionOrderCompletion's own operator_id, which is
    # the durable per-completion audit trail; this is a single denormalized
    # convenience field for shop-floor display.
    started_operator_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_table.id", name="fk_production_order_started_operator_id"),
        nullable=True,
        index=True,
    )
    started_operator: Mapped["UserOrmModel | None"] = relationship(
        "src.modules.platform.adapters.outbound.persistence.models.user_model.UserOrmModel",
        foreign_keys=[started_operator_id],
        lazy="raise_on_sql",
    )

    # Frozen once by StartProductionOrder from planned_end at the moment
    # of the order's first start, never rewritten afterward. See
    # production_order.py's matching field docstring.
    planned_end_at_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    machine_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("production_machine_table.id", name="fk_production_order_machine_id"),
        nullable=True,
        index=True,
    )
    machine: Mapped["ProductionMachineOrmModel | None"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.production_machine_model.ProductionMachineOrmModel",
        foreign_keys=[machine_id],
        lazy="raise_on_sql",
    )

    machine_pool_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("machine_pool_table.id", name="fk_production_order_machine_pool_id"),
        nullable=True,
        index=True,
    )
    machine_pool: Mapped["MachinePoolOrmModel | None"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.machine_pool_model.MachinePoolOrmModel",
        foreign_keys=[machine_pool_id],
        lazy="raise_on_sql",
    )

    # Not unique: several production orders may reference the same internal
    # lot position to allow parallel same-step splitting.
    lot_position_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "lot_position_table.id",
            name="fk_production_order_lot_position_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    lot_position: Mapped["LotPositionOrmModel"] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model.LotPositionOrmModel",
        foreign_keys=[lot_position_id],
        # Stays a plain lazy load: change_tracking resolves this row's lot
        # through it inside after_flush, where a lazy load is legal (also
        # under async, which runs flush in a greenlet). Readers that map it
        # load it explicitly.
        lazy="select",
    )

    completions: Mapped[list["ProductionOrderCompletionOrmModel"]] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.production_order_completion_model.ProductionOrderCompletionOrmModel",
        back_populates="production_order",
        order_by="ProductionOrderCompletionOrmModel.id",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )

    files: Mapped[list["ProductionOrderFileOrmModel"]] = relationship(
        "src.modules.fulfillment.adapters.outbound.persistence.models.production_order_file_model.ProductionOrderFileOrmModel",
        back_populates="production_order",
        order_by="ProductionOrderFileOrmModel.id",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )
