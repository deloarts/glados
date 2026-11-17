"""SQL predicates behind the lots table filters of the ProductionLot repository.

The actionable and coverable predicates mirror the frontend's panel checks
and the domain's remaining-quantity rule as correlated subqueries, so a
filtered page agrees with what each panel offers. The column filters below
them stay portable between SQLite and Postgres.
"""

from collections.abc import Callable
from datetime import date as dt
from datetime import tzinfo
from typing import cast

from sqlalchemy import and_
from sqlalchemy import exists
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model import (
    FabricationMethodOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
    SourceItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_type_model import (
    SourceItemTypeOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_step_model import (
    LotStepOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.machine_pool_model import (
    MachinePoolOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.machine_pool_model import (
    machine_pool_machine_table,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_allocation_model import (
    MadeItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
    MadeItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_machine_model import (
    machine_fabrication_method_table,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_allocation_model import (
    SourceItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.fulfillment.domain.value_objects.lot_status import TERMINAL_LOT_STATUSES
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    LotFilterDto,
)
from src.modules.platform.adapters.outbound.persistence.date_range import day_after_utc
from src.modules.platform.adapters.outbound.persistence.date_range import day_start_utc
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.localized_text_sql import localized_contains


def _position_remaining_expr(lp: type[LotPositionOrmModel]) -> ColumnElement[float]:
    """lot_rules.compute_position_remaining as a correlated subquery. A
    canceled order line no longer commits any of the position, a line closed
    short commits what it holds beside the line that took the rest, and a
    canceled production order commits only the pieces it completed."""
    return (
        lp.quantity
        - func.coalesce(
            select(func.sum(OrderItemOrmModel.quantity))
            .where(
                OrderItemOrmModel.lot_position_id == lp.id,
                OrderItemOrmModel.canceled_at.is_(None),
            )
            .scalar_subquery(),
            0.0,
        )
        - func.coalesce(
            select(func.sum(ProductionOrderOrmModel.quantity))
            .where(
                ProductionOrderOrmModel.lot_position_id == lp.id,
                ProductionOrderOrmModel.status != ProductionOrderStatus.CANCELED.value,
            )
            .scalar_subquery(),
            0.0,
        )
        - func.coalesce(
            select(func.sum(ProductionOrderOrmModel.quantity_completed))
            .where(
                ProductionOrderOrmModel.lot_position_id == lp.id,
                ProductionOrderOrmModel.status == ProductionOrderStatus.CANCELED.value,
            )
            .scalar_subquery(),
            0.0,
        )
    )


def _position_actionable_for_machines(lp: type[LotPositionOrmModel]) -> ColumnElement[bool]:
    """A position the Manage Production panel can act on: unrouted with
    quantity left, or internal with an order lacking a machine. Manual
    positions are excluded, since their orders never get a machine.
    Canceled and completed positions are excluded too, because a forced
    cascade keeps kind and quantity, so an unrouted position would look
    open forever."""
    needs_machine = exists().where(
        ProductionOrderOrmModel.lot_position_id == lp.id,
        ProductionOrderOrmModel.machine_id.is_(None),
    )
    return and_(
        lp.status.notin_([LotPositionStatus.CANCELED.value, LotPositionStatus.COMPLETED.value]),
        or_(
            and_(
                lp.kind.in_([LotPositionKind.UNASSIGNED.value, LotPositionKind.EXTERNAL.value]),
                _position_remaining_expr(lp) > 0,
            ),
            and_(
                lp.kind.in_([LotPositionKind.INTERNAL.value, LotPositionKind.MIXED.value]),
                needs_machine,
                ~_position_is_manual_predicate(lp),
            ),
        ),
    )


def _live_lot() -> ColumnElement[bool]:
    """The lot is not terminal, so its positions can still take work. A
    force-completed or scrapped lot can keep positions that are neither
    complete nor canceled."""
    return ProductionLotOrmModel.status.notin_(sorted(TERMINAL_LOT_STATUSES))


def _actionable_lot_exists(mode: str) -> ColumnElement[bool]:
    """Lots with something to act on in the given panel, mirroring the
    frontend's checks. Only a lot that is not terminal has anything to act
    on. For `source` it is lot-level: such a lot whose demand is missing or
    still open.
    """
    plot = ProductionLotOrmModel
    if mode == "source":
        return and_(
            _live_lot(),
            or_(
                plot.input_demand_id.is_(None),
                exists().where(
                    SourceItemDemandItemOrmModel.id == plot.input_demand_id,
                    SourceItemDemandItemOrmModel.status == SourceItemDemandStatus.OPEN.value,
                ),
            ),
        )

    lp = LotPositionOrmModel
    if mode == "orders":
        # Excluded as in _position_actionable_for_machines. Only a live line
        # supplies the position; one beside a canceled line can be ordered.
        predicate = and_(
            lp.status.notin_([LotPositionStatus.CANCELED.value, LotPositionStatus.COMPLETED.value]),
            ~exists().where(
                OrderItemOrmModel.lot_position_id == lp.id,
                OrderItemOrmModel.canceled_at.is_(None),
            ),
            _position_remaining_expr(lp) > 0,
        )
    else:
        predicate = _position_actionable_for_machines(lp)

    return and_(_live_lot(), exists().where(lp.lot_id == plot.id, predicate))


# ── Lots table column filters ────────────────────────────────────────
#
# Everything below runs on SQLite (the test suite) and Postgres alike, so
# it sticks to COALESCE, EXISTS, SUM and correlated scalar subqueries and
# never reaches for a dialect-specific cast or date function. Timestamp
# columns are compared against the half-open interval of the days in the
# tenant's timezone `zone` from date_range.py, plain Date columns inclusively.


def _timestamp_day_in_range(
    ts: ColumnElement[dt | None] | InstrumentedAttribute[dt | None],
    date_from: dt | None,
    date_to: dt | None,
    zone: tzinfo,
) -> ColumnElement[bool]:
    """Calendar-day range check on a tz-aware timestamp expression, the days
    read in `zone`. A NULL timestamp never matches, so callers need no
    separate IS NOT NULL."""
    clauses: list[ColumnElement[bool]] = []
    if date_from is not None:
        clauses.append(ts >= day_start_utc(date_from, zone))
    if date_to is not None:
        clauses.append(ts < day_after_utc(date_to, zone))
    return and_(ts.is_not(None), *clauses)


def _date_in_range(
    day: ColumnElement[dt | None] | InstrumentedAttribute[dt | None],
    date_from: dt | None,
    date_to: dt | None,
) -> ColumnElement[bool]:
    """Inclusive range check on a plain Date expression. NULL never matches."""
    clauses: list[ColumnElement[bool]] = []
    if date_from is not None:
        clauses.append(day >= date_from)
    if date_to is not None:
        clauses.append(day <= date_to)
    return and_(day.is_not(None), *clauses)


def _coalesced_day_in_range(
    ts: InstrumentedAttribute[dt | None],
    fallback_day: InstrumentedAttribute[dt | None],
    date_from: dt | None,
    date_to: dt | None,
    zone: tzinfo,
) -> ColumnElement[bool]:
    """Range check on the timestamp's day, else the fallback date. Two
    branches, because casting a timestamp to a date is dialect-specific."""
    return or_(
        _timestamp_day_in_range(ts, date_from, date_to, zone),
        and_(ts.is_(None), _date_in_range(fallback_day, date_from, date_to)),
    )


def _target_date_expr() -> ColumnElement[dt | None]:
    """The lot's target date as a correlated subquery, the same rule as
    describe_lot_target_dates."""
    earliest_demand_date = (
        select(func.min(MadeItemDemandItemOrmModel.desired_delivery_date))
        .select_from(MadeItemAllocationOrmModel)
        .join(
            MadeItemDemandItemOrmModel,
            MadeItemDemandItemOrmModel.id == MadeItemAllocationOrmModel.demand_item_id,
        )
        .where(MadeItemAllocationOrmModel.lot_id == ProductionLotOrmModel.id)
        .correlate(ProductionLotOrmModel)
        .scalar_subquery()
    )
    return func.coalesce(ProductionLotOrmModel.required_delivery_date, earliest_demand_date)


def _source_text_predicate(
    term: str, source_made_item: type[MadeItemOrmModel]
) -> ColumnElement[bool]:
    """Substring match over the display fields of the lot's material
    source. `source_made_item` is an alias, because the plain made item
    class is already joined for the lot's own item."""
    return or_(
        contains_ci(BoughtItemOrmModel.article_name, term),
        contains_ci(BoughtItemOrmModel.order_code_1, term),
        contains_ci(SourceItemOrmModel.dimension, term),
        contains_ci(SourceItemOrmModel.material, term),
        localized_contains(SourceItemTypeOrmModel.name, term),
        contains_ci(source_made_item.part_number, term),
        contains_ci(source_made_item.article_name, term),
    )


def _source_dimension_predicate(
    term: str, source_made_item: type[MadeItemOrmModel]
) -> ColumnElement[bool]:
    """Substring match over the first line of the source cell: what names
    the material, whichever kind of item supplies it."""
    return or_(
        contains_ci(BoughtItemOrmModel.article_name, term),
        contains_ci(BoughtItemOrmModel.order_code_1, term),
        contains_ci(SourceItemOrmModel.dimension, term),
        contains_ci(source_made_item.part_number, term),
        contains_ci(source_made_item.article_name, term),
    )


def _source_type_predicate(term: str) -> ColumnElement[bool]:
    """Substring match over the second line of a source item's cell, its
    type and material. Bought and made sources have no type, so they never
    match."""
    return or_(
        localized_contains(SourceItemTypeOrmModel.name, term),
        contains_ci(SourceItemOrmModel.material, term),
    )


def _source_status_exists(status: str) -> ColumnElement[bool]:
    """The lot's linked input demand carries exactly this stored status."""
    return exists().where(
        SourceItemDemandItemOrmModel.id == ProductionLotOrmModel.input_demand_id,
        SourceItemDemandItemOrmModel.status == status,
    )


def _source_delivery_exists(
    date_from: dt | None, date_to: dt | None, zone: tzinfo
) -> ColumnElement[bool]:
    """Some order item behind the input demand arrives within the range.
    The cell shows only the deciding item, but matching any is enough for a
    list filter."""
    return exists().where(
        SourceItemAllocationOrmModel.demand_item_id == ProductionLotOrmModel.input_demand_id,
        SourceItemAllocationOrmModel.order_item_id == OrderItemOrmModel.id,
        _coalesced_day_in_range(
            OrderItemOrmModel.delivery_date,
            OrderItemOrmModel.expected_delivery_date,
            date_from,
            date_to,
            zone,
        ),
    )


def _step_display_status_predicate(lp: type[LotPositionOrmModel], key: str) -> ColumnElement[bool]:
    """Maps the displayed position status back to stored status and kind,
    mirroring the frontend's lotPositionStatusKey, so "pending" never
    includes "allocated"."""
    pending = LotPositionStatus.PENDING.value
    ordered_or_queued = LotPositionStatus.ORDERED_OR_QUEUED.value
    allocated_kinds = [LotPositionKind.EXTERNAL.value, LotPositionKind.MIXED.value]
    if key == "pending":
        return and_(lp.status == pending, lp.kind.notin_(allocated_kinds))
    if key == "allocated":
        return and_(lp.status == pending, lp.kind.in_(allocated_kinds))
    if key == "queued":
        return and_(lp.status == ordered_or_queued, lp.kind == LotPositionKind.INTERNAL.value)
    if key == "ordered":
        return and_(lp.status == ordered_or_queued, lp.kind == LotPositionKind.EXTERNAL.value)
    if key == "ordered_or_queued":
        return and_(
            lp.status == ordered_or_queued,
            lp.kind.notin_([LotPositionKind.INTERNAL.value, LotPositionKind.EXTERNAL.value]),
        )
    return lp.status == key


def _position_sum_expr(
    lp: type[LotPositionOrmModel],
    column_expr: ColumnElement[float | None] | InstrumentedAttribute[int | None],
) -> ColumnElement[float | None]:
    """SUM of a per-step minutes expression over the position's steps, the
    figure the setup and per-piece cells show. NULL when no step carries a
    value, which never matches a range."""
    return (
        select(func.sum(column_expr))
        .where(LotStepOrmModel.position_id == lp.id)
        .correlate(lp)
        .scalar_subquery()
    )


def _step_planned_start_exists(
    lp: type[LotPositionOrmModel], date_from: dt | None, date_to: dt | None, zone: tzinfo
) -> ColumnElement[bool]:
    """Some live order of the position starts within the range."""
    po = ProductionOrderOrmModel
    return exists().where(
        po.lot_position_id == lp.id,
        po.status != ProductionOrderStatus.CANCELED.value,
        _timestamp_day_in_range(
            func.coalesce(po.actual_start, po.planned_start), date_from, date_to, zone
        ),
    )


def _step_planned_end_predicate(
    lp: type[LotPositionOrmModel], date_from: dt | None, date_to: dt | None, zone: tzinfo
) -> ColumnElement[bool]:
    """Some entry of the position ends within the range: a live order, the
    live order line, or without one the scheduler's forecast."""
    po = ProductionOrderOrmModel
    live_line = and_(
        OrderItemOrmModel.lot_position_id == lp.id, OrderItemOrmModel.canceled_at.is_(None)
    )
    order_item_linked = exists().where(live_line)
    return or_(
        exists().where(
            po.lot_position_id == lp.id,
            po.status != ProductionOrderStatus.CANCELED.value,
            _timestamp_day_in_range(
                func.coalesce(po.actual_end, po.planned_end), date_from, date_to, zone
            ),
        ),
        exists().where(
            live_line,
            _coalesced_day_in_range(
                OrderItemOrmModel.delivery_date,
                OrderItemOrmModel.expected_delivery_date,
                date_from,
                date_to,
                zone,
            ),
        ),
        and_(~order_item_linked, _date_in_range(lp.planned_delivery_date, date_from, date_to)),
    )


def _step_delivery_predicate(
    lp: type[LotPositionOrmModel], date_from: dt | None, date_to: dt | None, zone: tzinfo
) -> ColumnElement[bool]:
    """An actual completion or delivery of the position falls within the
    range; projections never count."""
    po = ProductionOrderOrmModel
    return or_(
        exists().where(
            po.lot_position_id == lp.id,
            po.status == ProductionOrderStatus.COMPLETED.value,
            _timestamp_day_in_range(po.actual_end, date_from, date_to, zone),
        ),
        exists().where(
            OrderItemOrmModel.lot_position_id == lp.id,
            OrderItemOrmModel.status == OrderItemStatus.DELIVERED.value,
            _timestamp_day_in_range(OrderItemOrmModel.delivery_date, date_from, date_to, zone),
        ),
    )


def _step_predicate_specs(
    filters: LotFilterDto, lp: type[LotPositionOrmModel], zone: tzinfo
) -> list[tuple[object, Callable[[], ColumnElement[bool]]]]:
    """(is_active, build_predicate) per step filter, ANDed inside one
    EXISTS by _step_exists. The date filters are days in `zone`."""
    return [
        (
            filters.step_fabrication_method_id is not None,
            lambda: exists().where(
                LotStepOrmModel.position_id == lp.id,
                LotStepOrmModel.fabrication_method_id == filters.step_fabrication_method_id,
            ),
        ),
        (
            filters.step_inspection_method_id is not None,
            lambda: exists().where(
                LotStepOrmModel.position_id == lp.id,
                LotStepOrmModel.inspection_method_id == filters.step_inspection_method_id,
            ),
        ),
        (
            bool(filters.step_status),
            lambda: _step_display_status_predicate(lp, cast(str, filters.step_status)),
        ),
        (
            filters.step_planned_start_from or filters.step_planned_start_to,
            lambda: _step_planned_start_exists(
                lp, filters.step_planned_start_from, filters.step_planned_start_to, zone
            ),
        ),
        (
            filters.step_planned_end_from or filters.step_planned_end_to,
            lambda: _step_planned_end_predicate(
                lp, filters.step_planned_end_from, filters.step_planned_end_to, zone
            ),
        ),
        (
            filters.step_delivery_from or filters.step_delivery_to,
            lambda: _step_delivery_predicate(
                lp, filters.step_delivery_from, filters.step_delivery_to, zone
            ),
        ),
        (
            bool(filters.step_note),
            lambda: exists().where(
                LotStepOrmModel.position_id == lp.id,
                contains_ci(LotStepOrmModel.note, cast(str, filters.step_note)),
            ),
        ),
        *_step_minutes_range_specs(filters, lp),
    ]


def _step_minutes_range_specs(
    filters: LotFilterDto, lp: type[LotPositionOrmModel]
) -> list[tuple[object, Callable[[], ColumnElement[bool]]]]:
    """Setup and per-piece minute bounds, each independently active."""
    setup_sum = _position_sum_expr(lp, LotStepOrmModel.estimated_setup_minutes)
    per_piece_sum = _position_sum_expr(
        lp,
        func.coalesce(
            LotStepOrmModel.estimated_minutes_per_piece, LotStepOrmModel.time_budget_per_piece
        ),
    )
    return [
        (filters.step_setup_min is not None, lambda: setup_sum >= filters.step_setup_min),
        (filters.step_setup_max is not None, lambda: setup_sum <= filters.step_setup_max),
        (
            filters.step_per_piece_min is not None,
            lambda: per_piece_sum >= filters.step_per_piece_min,
        ),
        (
            filters.step_per_piece_max is not None,
            lambda: per_piece_sum <= filters.step_per_piece_max,
        ),
    ]


def _step_exists(filters: LotFilterDto, zone: tzinfo) -> ColumnElement[bool] | None:
    """One EXISTS over the lot's positions with every active step filter
    ANDed inside, so all of them describe the same position: "milling and
    queued" means a position that is both, never a milled position plus a
    separately queued one. The lot matches as a whole. None when no step
    filter is set. The date filters are days in `zone`, the tenant's."""
    lp = LotPositionOrmModel
    predicates = [
        build() for is_active, build in _step_predicate_specs(filters, lp, zone) if is_active
    ]
    if not predicates:
        return None
    return exists().where(lp.lot_id == ProductionLotOrmModel.id, *predicates)


def _position_is_manual_predicate(lp: type[LotPositionOrmModel]) -> ColumnElement[bool]:
    """SQL mirror of production_order_rules.position_is_manual."""
    return ~exists().where(
        LotStepOrmModel.position_id == lp.id,
        LotStepOrmModel.fabrication_method_id == FabricationMethodOrmModel.id,
        FabricationMethodOrmModel.requires_machine.is_(True),
    )


def _position_uncovered_by_machine(
    lp: type[LotPositionOrmModel], machine_id: int
) -> ColumnElement[bool]:
    """True when the machine lacks a method a machine-requiring step needs."""
    return exists().where(
        LotStepOrmModel.position_id == lp.id,
        LotStepOrmModel.fabrication_method_id == FabricationMethodOrmModel.id,
        FabricationMethodOrmModel.requires_machine.is_(True),
        ~exists().where(
            machine_fabrication_method_table.c.machine_id == machine_id,
            machine_fabrication_method_table.c.fabrication_method_id
            == LotStepOrmModel.fabrication_method_id,
        ),
    )


def _position_uncovered_by_pool(
    lp: type[LotPositionOrmModel], pool_id: int | ColumnElement[int] | InstrumentedAttribute[int]
) -> ColumnElement[bool]:
    """True when some pool member lacks a method a machine-requiring step
    needs, since a pool covers a position only if every member does. The
    query linter's Cartesian product warning here is benign.

    `.correlate(lp, MachinePoolOrmModel)` is load-bearing for the any-pool
    filter, which nests this EXISTS two levels deep: auto-correlation does
    not reach `lp` that far and would join every lot position instead.
    Both names are needed, because correlate() replaces the automatic set
    and naming only `lp` would decorrelate the pool."""
    return (
        exists()
        .where(
            LotStepOrmModel.position_id == lp.id,
            LotStepOrmModel.fabrication_method_id == FabricationMethodOrmModel.id,
            FabricationMethodOrmModel.requires_machine.is_(True),
            machine_pool_machine_table.c.pool_id == pool_id,
            ~exists().where(
                machine_fabrication_method_table.c.machine_id
                == machine_pool_machine_table.c.machine_id,
                machine_fabrication_method_table.c.fabrication_method_id
                == LotStepOrmModel.fabrication_method_id,
            ),
        )
        .correlate(lp, MachinePoolOrmModel)
    )


def _pool_has_machines(
    pool_id: int | ColumnElement[int] | InstrumentedAttribute[int],
) -> ColumnElement[bool]:
    return exists().where(machine_pool_machine_table.c.pool_id == pool_id)


def _coverable_lot_exists(
    *,
    machine_id: int | None = None,
    pool_id: int | None = None,
    any_pool: bool = False,
) -> ColumnElement[bool]:
    """Lots with an actionable position the given machine, pool or any pool
    could take, mirroring the capability rules; an empty pool covers
    nothing.

    For a specific machine or pool, manual positions are excluded
    explicitly: they need no machine, and the negated EXISTS would count
    them as covered by everything. The any-pool filter keeps them, matching
    the frontend before a target is picked.
    """
    lp = LotPositionOrmModel
    is_manual = _position_is_manual_predicate(lp)

    if machine_id is not None:
        coverage: ColumnElement[bool] = and_(
            ~is_manual, ~_position_uncovered_by_machine(lp, machine_id)
        )
    elif pool_id is not None:
        coverage = and_(
            ~is_manual, _pool_has_machines(pool_id), ~_position_uncovered_by_pool(lp, pool_id)
        )
    else:
        assert any_pool
        pool = MachinePoolOrmModel
        is_covered_by_some_pool = exists().where(
            pool.archived.is_(False),
            _pool_has_machines(pool.id),
            ~_position_uncovered_by_pool(lp, pool.id),
        )
        coverage = or_(is_manual, is_covered_by_some_pool)

    predicate = and_(_position_actionable_for_machines(lp), coverage)
    return and_(_live_lot(), exists().where(lp.lot_id == ProductionLotOrmModel.id, predicate))


def _status_clause(filters: LotFilterDto) -> ColumnElement[bool]:
    """`statuses` wins over `status` when both are set."""
    if filters.statuses:
        return ProductionLotOrmModel.status.in_(filters.statuses)
    return ProductionLotOrmModel.status == filters.status


def _coverable_by_clause(filters: LotFilterDto) -> ColumnElement[bool]:
    """At most one coverable_by filter is set (request validation)."""
    if filters.coverable_by_machine_id is not None:
        return _coverable_lot_exists(machine_id=filters.coverable_by_machine_id)
    if filters.coverable_by_pool_id is not None:
        return _coverable_lot_exists(pool_id=filters.coverable_by_pool_id)
    assert filters.coverable_by_any_pool
    return _coverable_lot_exists(any_pool=True)


def _todo_candidate_clause(horizon: dt) -> ColumnElement[bool]:
    """The lots the Todo page can turn into a task: one on hold, one whose
    material source waits for approval while it is still open, and a draft
    or partially planned lot without a delivery date or due by `horizon`.
    The page decides the bucket, so this only keeps out the rows that can
    never give a task."""
    lot = ProductionLotOrmModel
    return or_(
        lot.status == LotStatus.ON_HOLD.value,
        and_(
            lot.source_approval_status == SourceApprovalStatus.PENDING.value,
            lot.status.notin_([LotStatus.COMPLETED.value, LotStatus.CANCELED.value]),
        ),
        and_(
            lot.status.in_([LotStatus.DRAFT.value, LotStatus.PARTIALLY_PLANNED.value]),
            or_(lot.required_delivery_date.is_(None), lot.required_delivery_date <= horizon),
        ),
    )
