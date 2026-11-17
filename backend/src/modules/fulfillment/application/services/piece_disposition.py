"""Shared disposition for pieces that leave a lot short, used by scrap during
production, by inspection rejects and by pieces lost at goods receipt, so
all three behave identically. Nothing here commits or writes a status.

Removing pieces at a position closes the lot short permanently: the lot, the
position and every later position lose the removed pieces, and earlier
positions keep their quantity, since their output also fed the removed
pieces (lot_rules.shrink_lot_for_scrap). The caller refuses a removal that
would take a position below what it already completed
(lot_rules.assert_disposition_keeps_completed) before it writes anything.
The live work of every shrunk position is then cut back to what the
position still needs (lot_rules.plan_commitment_cuts): production orders
that have not started first, then running ones, newest first and never
below what they processed, then a line not yet ordered; a cut that leaves
nothing done cancels the order or the line. A lot left with nothing to
produce instead cancels all of its live work and its raw material demand.

A rework lot (inspection only) and, unless opted out, a replacement lot are
spawned, and the origin lot's demand coverage moves onto them
(reallocate_lot_coverage). Every row written here is registered with the
caller's lifecycle reconciler, which derives the statuses when the caller
runs it, after the disposition, the made demands whose allocations moved
included.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from typing import Protocol

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.dto.production_lot_dto import CreateLotCommand
from src.modules.fulfillment.application.dto.production_order_dto import CreatedLotResult
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.lot_cascades import cancel_input_demand
from src.modules.fulfillment.application.services.lot_cascades import cancel_line
from src.modules.fulfillment.application.services.lot_cascades import cancel_live_work
from src.modules.fulfillment.application.services.lot_cascades import cancel_production_order
from src.modules.fulfillment.application.services.lot_cascades import lines_to_settle_event
from src.modules.fulfillment.application.services.lot_cascades import settle_input_demand
from src.modules.fulfillment.application.services.production_order_interruptions import (
    close_open_interruptions,
)
from src.modules.fulfillment.domain.entities.lot_event import LotEvent
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.events.lot_events import LotCreated
from src.modules.fulfillment.domain.events.lot_events import LotSupplierLinesToSettle
from src.modules.fulfillment.domain.services.lifecycle.demand import fit_in_fill_order
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.lot_rules import Commitment
from src.modules.fulfillment.domain.services.lot_rules import CommitmentCut
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.services.lot_rules import plan_commitment_cuts
from src.modules.fulfillment.domain.services.lot_rules import shrink_lot_for_scrap
from src.modules.fulfillment.domain.services.lot_rules import split_quantity_by_largest_remainder
from src.modules.fulfillment.domain.services.production_order_rules import (
    compute_estimated_duration_minutes,
)
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_origin_disposition import LotOriginDisposition
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.production_status import (
    TERMINAL_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_interruption_repository import (
    IProductionOrderInterruptionRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.quantities import is_zero_quantity
from src.modules.platform.domain.services.quantities import quantity_ge
from src.shared_kernel.domain.events.base import DomainEvent
from src.shared_kernel.domain.services.changelog_service import append_changelog

# A line the supplier has not been asked to deliver yet; a disposition may
# cut it, an ordered one it leaves to the buyer.
_CUTTABLE_LINES = frozenset({OrderItemStatus.PENDING, OrderItemStatus.REQUESTED})
# Demands owed nothing more, which take no share of a follow-up lot.
_FINISHED_DEMANDS = frozenset({MadeItemDemandStatus.FULFILLED, MadeItemDemandStatus.CANCELED})
# The decimals allocation shares are split at, as split_quantity_by_largest_remainder.
_SHARE_DECIMALS = 6


class LotCreator(Protocol):
    """The lot creation a disposition spawns follow-up lots with, without a
    commit (CreateLot.create_no_commit)."""

    async def create_no_commit(
        self,
        actor: User,
        cmd: CreateLotCommand,
        *,
        origin_lot_id: int | None = None,
        origin_disposition: LotOriginDisposition | None = None,
        forced_source_made_item_id: int | None = None,
        create_source_item_demand: bool = True,
        check_create_permission: bool = True,
    ) -> ProductionLot: ...


@dataclass
class DispositionOutcome:
    """The follow-up lots, the events the caller publishes, the made
    demands whose allocations the disposition changed, which it registers
    with the caller's reconciler, and the projects whose lot quantities it
    changed, whose time budgets the caller recomputes after its run."""

    created_lots: list[CreatedLotResult] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)
    made_demand_ids: set[int] = field(default_factory=set)
    project_ids: set[int] = field(default_factory=set)


@dataclass(frozen=True)
class DispositionRepositories:
    """What a disposition writes besides the lot and its allocations: the
    live work of the lot and its raw material demand, registered with
    `reconciler`, the caller's."""

    production_orders: IProductionOrderRepository
    order_items: IOrderItemRepository
    orders: IOrderRepository
    interruptions: IProductionOrderInterruptionRepository
    source_item_demands: ISourceItemDemandRepository
    source_item_allocations: ISourceItemAllocationRepository
    reconciler: LifecycleReconciler
    # Settles the raw material demand of a lot that reaches zero as a lot
    # cancel does; without it the demand is canceled.
    bought_allocations: IBoughtItemAllocationRepository | None = None


async def apply_disposition(
    *,
    lots_repo: IProductionLotRepository,
    work: DispositionRepositories,
    made_item_demand_repo: IMadeItemDemandItemRepository,
    made_item_allocation_repo: IMadeItemAllocationRepository,
    create_lot: LotCreator,
    actor: User,
    lot: ProductionLot,
    position: LotPosition,
    removed_quantity: float,
    quantity_rework: float,
    quantity_scrap: float,
    create_replacement: bool,
    closing_event: LotEvent,
    replacement_note: str,
    accepted_now: float = 0.0,
    replacement_required_delivery_date: date | None = None,
    replacement_priority: str | None = None,
    now: datetime,
) -> DispositionOutcome:
    """Applies the disposition of `removed_quantity` pieces at `position`,
    see the module docstring. `accepted_now` are the pieces the caller's own
    operation accepted at the position, which its stored completed count
    does not hold yet. The scrap path passes the origin lot's date and
    priority for its replacement; None prefills them."""
    shrunk = shrink_lot_for_scrap(lot, position, removed_quantity)
    lot.quantity_scrapped += quantity_scrap
    lot.changed = now
    if is_zero_quantity(lot.quantity):
        # A lot with nothing left ends, and its live orders are canceled
        # below, so no hold is left to lift, as a lot cancel clears it.
        lot.held_at = None
    await lots_repo.save(lot)
    for touched in shrunk:
        await lots_repo.save_position(touched)
    await lots_repo.record_event(closing_event)
    work.reconciler.touch_lots([lot.id])

    settle_event: LotSupplierLinesToSettle | None = None
    if is_zero_quantity(lot.quantity):
        reason = f"lot {lot.lot_number!r} has nothing left to produce"
        # As a lot cancel does: an ordered supplier line is not canceled
        # behind the supplier's back but left open and named to purchasing.
        left_open = await cancel_live_work(
            lot,
            lot.positions,
            actor,
            now,
            reason=reason,
            lot_repo=lots_repo,
            order_repo=work.production_orders,
            order_item_repo=work.order_items,
            parent_order_repo=work.orders,
            interruption_repo=work.interruptions,
            reconciler=work.reconciler,
            keep_ordered_lines=True,
        )
        if work.bought_allocations is not None:
            # As a lot cancel does: a demand whose material was placed or
            # arrived is fulfilled at what arrived, its open lines named.
            settled = await settle_input_demand(
                lot,
                actor,
                now,
                reason=reason,
                source_item_demands=work.source_item_demands,
                source_allocations=work.source_item_allocations,
                bought_allocations=work.bought_allocations,
                order_item_repo=work.order_items,
                reconciler=work.reconciler,
            )
            left_open = [*left_open, *settled.open_lines]
        else:
            await cancel_input_demand(
                work.source_item_demands,
                work.source_item_allocations,
                work.reconciler,
                actor,
                lot,
                now,
                reason=reason,
            )
        settle_event = await lines_to_settle_event(
            work.orders, lot, actor, ended="scrapped", open_lines=left_open, canceled_lines=[]
        )
    else:
        for shrunk_position in shrunk:
            await _cut_commitments(
                lots_repo,
                work,
                actor,
                lot,
                shrunk_position,
                accepted_now if shrunk_position.id == position.id else 0.0,
                now,
            )

    outcome = DispositionOutcome(project_ids={lot.project_id})
    if settle_event is not None:
        outcome.events.append(settle_event)
    rework_lot = await _create_rework_lot(
        create_lot, lots_repo, actor, lot, quantity_rework, removed_quantity, outcome
    )
    replacement_lot = await _create_replacement_lot_or_skip(
        create_lot,
        lots_repo,
        actor,
        lot,
        quantity_scrap,
        create_replacement,
        replacement_note,
        replacement_required_delivery_date,
        replacement_priority,
        outcome,
    )
    outcome.made_demand_ids = await reallocate_lot_coverage(
        lot=lot,
        made_item_demand_repo=made_item_demand_repo,
        made_item_allocation_repo=made_item_allocation_repo,
        rework_lot=rework_lot,
        replacement_lot=replacement_lot,
        quantity_rework=quantity_rework,
        quantity_scrap=quantity_scrap,
    )
    work.reconciler.touch_demands(LifecycleAggregate.MADE_DEMANDS, outcome.made_demand_ids)
    outcome.events.extend(
        LotCreated(
            lot_id=created.id,
            made_item_id=created.made_item_id,
            creator_id=created.creator_id,
        )
        for created in (rework_lot, replacement_lot)
        if created is not None
    )
    return outcome


# ── Cutting the live work of a shrunk position ──────────────────────────


async def _cut_commitments(
    lots_repo: IProductionLotRepository,
    work: DispositionRepositories,
    actor: User,
    lot: ProductionLot,
    position: LotPosition,
    accepted_now: float,
    now: datetime,
) -> None:
    """Cuts the position's live production orders and its live line back to
    what the position still needs, see the module docstring."""
    orders = {
        o.id: o
        for o in await work.production_orders.get_by_lot_position_ids([position.id], refresh=True)
        if o.status not in TERMINAL_PRODUCTION_ORDER_STATUSES
    }
    lines = {
        line.id: line
        for line in await work.order_items.get_by_lot_position_ids([position.id], refresh=True)
        if line.canceled_at is None
    }
    commitments = [
        Commitment(
            id=o.id,
            is_line=False,
            quantity=o.quantity,
            done=o.pieces_processed,
            queued=o.status == ProductionOrderStatus.QUEUED,
        )
        for o in orders.values()
    ] + [
        Commitment(
            id=line.id,
            is_line=True,
            quantity=line.quantity,
            done=line.quantity_settled,
            cuttable=line.status in _CUTTABLE_LINES,
        )
        for line in lines.values()
    ]
    reason = f"lot {lot.lot_number!r} was closed short to {lot.quantity:.3f}"
    for cut in plan_commitment_cuts(position, commitments, accepted_now=accepted_now):
        if cut.commitment.is_line:
            await _cut_line(work, actor, lines[cut.commitment.id], cut, reason, now)
        else:
            await _cut_order(
                lots_repo, work, actor, lot, position, orders[cut.commitment.id], cut, reason, now
            )


async def _cut_order(
    lots_repo: IProductionLotRepository,
    work: DispositionRepositories,
    actor: User,
    lot: ProductionLot,
    position: LotPosition,
    order: ProductionOrder,
    cut: CommitmentCut,
    reason: str,
    now: datetime,
) -> None:
    """Lowers the order to the cut's quantity, with its duration sized to
    it, or cancels it when the cut leaves nothing. An order the cut ends,
    because it processed its new quantity, has its open interruptions
    closed."""
    if cut.cancels:
        await cancel_production_order(
            order,
            lot,
            actor,
            now,
            reason,
            lot_repo=lots_repo,
            order_repo=work.production_orders,
            interruption_repo=work.interruptions,
            reconciler=work.reconciler,
        )
        return
    old_quantity = order.quantity
    order.quantity = cut.quantity
    order.estimated_duration_minutes = compute_estimated_duration_minutes(
        position.steps, cut.quantity
    )
    order.changed = now
    order.changes = append_changelog(
        order.changes,
        actor.full_name,
        f"Quantity {old_quantity:.3f} → {cut.quantity:.3f}, {reason}.",
    )
    await work.production_orders.save(order)
    if quantity_ge(cut.commitment.done, cut.quantity):
        await close_open_interruptions(work.interruptions, order.id, now, actor.id)
    work.reconciler.touch_production_orders([order.id])


async def _cut_line(
    work: DispositionRepositories,
    actor: User,
    line: OrderItem,
    cut: CommitmentCut,
    reason: str,
    now: datetime,
) -> None:
    """Lowers a line not yet ordered to the cut's quantity, or cancels it
    when the cut leaves nothing. A position's line is a MADE line, which no
    demand allocation draws on."""
    if cut.cancels:
        await cancel_line(
            line, actor, now, reason, order_item_repo=work.order_items, reconciler=work.reconciler
        )
        return
    old_quantity = line.quantity
    line.quantity = cut.quantity
    line.changed = now
    line.changes = append_changelog(
        line.changes,
        actor.full_name,
        f"Quantity {old_quantity:.3f} → {cut.quantity:.3f} {line.unit}, {reason}.",
    )
    await work.order_items.save(line)
    work.reconciler.touch_order_items([line.id])


# ── Follow-up lots ───────────────────────────────────────────────────────


async def _create_rework_lot(
    create_lot: LotCreator,
    lots_repo: IProductionLotRepository,
    actor: User,
    lot: ProductionLot,
    quantity_rework: float,
    removed_quantity: float,
    outcome: DispositionOutcome,
) -> ProductionLot | None:
    """Spawns the rework lot of an inspection reject and records it on the
    origin lot's timeline."""
    if quantity_rework <= 0:
        return None
    rework_lot = await create_lot.create_no_commit(
        actor,
        CreateLotCommand(
            made_item_id=lot.made_item_id,
            project_id=lot.project_id,
            quantity=quantity_rework,
            note=f"Rework of {removed_quantity:.3f} rejected piece(s) from lot "
            f"{lot.lot_number} (QA reject).",
        ),
        origin_lot_id=lot.id,
        origin_disposition=LotOriginDisposition.REWORK,
        forced_source_made_item_id=lot.made_item_id,
        create_source_item_demand=False,
        check_create_permission=False,
    )
    outcome.created_lots.append(
        CreatedLotResult(
            id=rework_lot.id,
            lot_number=rework_lot.lot_number,
            disposition=LotOriginDisposition.REWORK,
        )
    )
    await lots_repo.record_event(
        build_lot_event(
            lot.id,
            actor,
            LotEventType.REWORK_LOT_CREATED,
            "lot",
            f"Rework lot {rework_lot.lot_number} created for {quantity_rework:.3f} piece(s).",
            entity_id=rework_lot.id,
            payload={
                "lot_id": rework_lot.id,
                "lot_number": rework_lot.lot_number,
                "quantity": quantity_rework,
            },
        )
    )
    return rework_lot


async def _create_replacement_lot_or_skip(
    create_lot: LotCreator,
    lots_repo: IProductionLotRepository,
    actor: User,
    lot: ProductionLot,
    quantity_scrap: float,
    create_replacement: bool,
    replacement_note: str,
    replacement_required_delivery_date: date | None,
    replacement_priority: str | None,
    outcome: DispositionOutcome,
) -> ProductionLot | None:
    """Spawns the replacement lot for scrapped pieces; an opt-out is
    recorded on the origin lot's timeline instead."""
    if quantity_scrap <= 0:
        return None
    if not create_replacement:
        await lots_repo.record_event(
            build_lot_event(
                lot.id,
                actor,
                LotEventType.REPLACEMENT_SKIPPED,
                "lot",
                f"No replacement lot created for {quantity_scrap:.3f} scrapped "
                "piece(s); demand coverage reduced instead.",
                payload={"quantity": quantity_scrap},
            )
        )
        return None
    replacement_lot = await create_lot.create_no_commit(
        actor,
        CreateLotCommand(
            made_item_id=lot.made_item_id,
            project_id=lot.project_id,
            quantity=quantity_scrap,
            note=replacement_note,
            required_delivery_date=replacement_required_delivery_date,
            priority=replacement_priority,
        ),
        origin_lot_id=lot.id,
        origin_disposition=LotOriginDisposition.REPLACEMENT,
        check_create_permission=False,
    )
    outcome.created_lots.append(
        CreatedLotResult(
            id=replacement_lot.id,
            lot_number=replacement_lot.lot_number,
            disposition=LotOriginDisposition.REPLACEMENT,
        )
    )
    await lots_repo.record_event(
        build_lot_event(
            lot.id,
            actor,
            LotEventType.REPLACEMENT_LOT_CREATED,
            "lot",
            f"Replacement lot {replacement_lot.lot_number} created for "
            f"{quantity_scrap:.3f} piece(s).",
            entity_id=replacement_lot.id,
            payload={
                "lot_id": replacement_lot.id,
                "lot_number": replacement_lot.lot_number,
                "quantity": quantity_scrap,
            },
        )
    )
    return replacement_lot


# ── Demand coverage ──────────────────────────────────────────────────────


async def reallocate_lot_coverage(
    *,
    lot: ProductionLot,
    made_item_demand_repo: IMadeItemDemandItemRepository,
    made_item_allocation_repo: IMadeItemAllocationRepository,
    rework_lot: ProductionLot | None = None,
    replacement_lot: ProductionLot | None = None,
    quantity_rework: float = 0.0,
    quantity_scrap: float = 0.0,
) -> set[int]:
    """Moves the demand coverage of a lot whose quantity just shrank to
    `lot.quantity` and returns the ids of the demands on it.

    The allocations shrink only by what they exceed the new quantity, cut
    from the end of the lot's fill order, the newest live demand first and a
    finished demand only after every live one (lifecycle/demand.py
    fit_in_fill_order). A lot of 10 with one allocation of 4 that closes at
    6 keeps the 4. The completed pieces fill the allocations oldest first,
    so cutting from the end never takes pieces that already reached a
    demand. This is a coverage-preserving cascade over the lot, not a user
    write on a terminal demand.

    The follow-up lots take back what the shrink cut from each live demand,
    no more: a demand's cut is split between the rework and the replacement
    lot in the ratio of their quantities, the rework part by largest
    remainder over the cuts and the replacement taking the rest, so a demand
    never ends above what it had across the origin and its follow-up lots.
    The part of a lot that is not created stays cut. A finished demand,
    FULFILLED or CANCELED, takes none, since nothing more is owed to it."""
    allocations = sorted(
        await made_item_allocation_repo.get_by_lot_id(lot.id), key=lambda a: a.demand_item_id
    )
    if not allocations:
        return set()
    finished = await _finished_demand_ids(
        made_item_demand_repo, {a.demand_item_id for a in allocations}
    )
    marked = [a.demand_item_id in finished for a in allocations]
    fitted = fit_in_fill_order([a.quantity for a in allocations], lot.quantity, marked)
    shrink_shares = [a.quantity - kept for a, kept in zip(allocations, fitted, strict=True)]
    rework_shares, scrap_shares = _follow_up_shares(
        [0.0 if done else cut for cut, done in zip(shrink_shares, marked, strict=True)],
        quantity_rework,
        quantity_scrap,
    )
    if rework_lot is None:
        rework_shares = [0.0] * len(allocations)
    if replacement_lot is None:
        scrap_shares = [0.0] * len(allocations)

    touched_demand_ids: set[int] = set()
    for allocation, shrink, rework_share, scrap_share in zip(
        allocations, shrink_shares, rework_shares, scrap_shares, strict=True
    ):
        await made_item_allocation_repo.save(
            MadeItemDemandAllocation(
                demand_item_id=allocation.demand_item_id,
                lot_id=lot.id,
                quantity=max(allocation.quantity - shrink, 0.0),
                source=allocation.source,
            )
        )
        for follow_up, share in ((rework_lot, rework_share), (replacement_lot, scrap_share)):
            if follow_up is not None and share > 0:
                await made_item_allocation_repo.save(
                    MadeItemDemandAllocation(
                        demand_item_id=allocation.demand_item_id,
                        lot_id=follow_up.id,
                        quantity=share,
                        source=allocation.source,
                    )
                )
        touched_demand_ids.add(allocation.demand_item_id)

    # Defense in depth: a new lot's allocations must fit its quantity.
    if rework_lot is not None:
        LotRules.assert_allocations_within_quantity(rework_lot.quantity, sum(rework_shares))
    if replacement_lot is not None:
        LotRules.assert_allocations_within_quantity(replacement_lot.quantity, sum(scrap_shares))
    return touched_demand_ids


async def _finished_demand_ids(
    made_item_demand_repo: IMadeItemDemandItemRepository | None, demand_ids: set[int]
) -> set[int]:
    if made_item_demand_repo is None or not demand_ids:
        return set()
    demands = await made_item_demand_repo.get_by_ids(sorted(demand_ids))
    return {d.id for d in demands if d.status in _FINISHED_DEMANDS}


def _follow_up_shares(
    cuts: list[float], quantity_rework: float, quantity_scrap: float
) -> tuple[list[float], list[float]]:
    """Each allocation's share of the rework and of the replacement lot:
    its cut split in the ratio of the two quantities, the rework part by
    largest remainder over the cuts and the replacement taking the rest, so
    the two shares of a demand add up to its cut."""
    total_cut = sum(cuts)
    removed = quantity_rework + quantity_scrap
    if total_cut <= 0 or removed <= 0:
        return [0.0] * len(cuts), [0.0] * len(cuts)
    rework_total = round(total_cut * quantity_rework / removed, _SHARE_DECIMALS)
    rework = split_quantity_by_largest_remainder(rework_total, cuts)
    scrap = [
        max(round(cut - share, _SHARE_DECIMALS), 0.0)
        for cut, share in zip(cuts, rework, strict=True)
    ]
    return rework, scrap
