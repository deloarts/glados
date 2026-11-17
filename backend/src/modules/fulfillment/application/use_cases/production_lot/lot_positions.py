"""
RegroupLotPositions (any non-terminal lot status, PUT /{id}/positions):
replace of the position grouping. A submitted group that exactly matches
an existing position's step set PRESERVES that position (same row, only
resequenced); every other group becomes a new position, with its steps'
position_id repointed BEFORE the orphaned old positions are deleted;
this ordering matters, since LotStep's FK to LotPosition cascades on
delete and steps must never be deleted here, only regrouped. Rejects
(via assert_positions_unassigned) only if a position whose membership
actually CHANGES is already assigned to a supplier order or machine,
those positions' step ranges are a physical fact once committed, not
just data, and deleting one out from under its OrderItem/ProductionOrder
FK would otherwise crash with a raw integrity error instead of a clean
rejection. Preserving unchanged groups is what keeps a lot with a
born-INTERNAL QA position (auto-queued at creation, see
create_lot._auto_queue_inspection_position) regroupable at all: the QA
singleton's membership can never change (validate_position_grouping),
so it rides along untouched while the fabrication positions regroup
around it.

AppendLotPosition (any non-terminal status): tail-append a new position
with brand-new ad-hoc steps. Never touches an existing position.

Both lock the lot through the request's lock plan before they read what
they check, and run the lifecycle reconciler before they commit, which
derives the new positions and the lot's status from them: a new position is
PENDING, so a planned lot that gains one is partially planned again.
"""

from collections.abc import Iterable

from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.errors import FabricationMethodArchivedError
from src.modules.catalogue.domain.errors import FabricationMethodNotFoundError
from src.modules.catalogue.domain.errors import InspectionMethodArchivedError
from src.modules.catalogue.domain.errors import InspectionMethodNotFoundError
from src.modules.catalogue.domain.policies.inspection_method_rules import seed_inspection_estimates
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.catalogue.ports.outbound.catalogue_queries import IFabricationMethodQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IInspectionMethodQueries
from src.modules.fulfillment.application.dto.production_lot_dto import AppendLotPositionCommand
from src.modules.fulfillment.application.dto.production_lot_dto import LotPositionResult
from src.modules.fulfillment.application.dto.production_lot_dto import RegroupLotPositionsCommand
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotPositionMapper
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.domain.errors import LotPositionGroupingInvalidError
from src.modules.fulfillment.domain.errors import LotPositionInUseError
from src.modules.fulfillment.domain.errors import LotPositionNotFoundError
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.services.lot_rules import assert_valid_step_role
from src.modules.fulfillment.domain.services.lot_rules import validate_position_grouping
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


async def locked_lot(
    reconciler: LifecycleReconciler, lots: IProductionLotRepository, lot_id: int
) -> ProductionLot:
    """Locks the lot through the request's lock plan and reads it again
    under the lock, for a structure edit or a lifecycle action to check and
    write."""
    await reconciler.lock_touched(also=AggregateIds.of({LifecycleAggregate.LOTS: [lot_id]}))
    return found_or_raise(
        await lots.get_by_id_for_update(lot_id), LotNotFoundError, f"Lot #{lot_id} not found."
    )


async def lock_quote_requests_of_positions(
    reconciler: LifecycleReconciler, lots: IProductionLotRepository, position_ids: list[int]
) -> None:
    """Touches and locks the quote requests with a line naming one of the
    positions, before a delete of the positions removes those lines, so the
    reconciler derives each request again without them. Quote requests come
    last in the lock order, so they lock after whatever the plan holds."""
    request_ids = await lots.get_quote_request_ids_of_positions(sorted(position_ids))
    if not request_ids:
        return
    reconciler.touch_quote_requests(request_ids)
    await reconciler.lock_plan.acquire(
        AggregateIds.of({LifecycleAggregate.QUOTE_REQUESTS: request_ids})
    )


async def lock_structure_edit(
    reconciler: LifecycleReconciler,
    lots: IProductionLotRepository,
    lot: ProductionLot,
    *,
    production_order_ids: Iterable[int] = (),
    deleted_position_ids: Iterable[int] = (),
    time_budgets: bool,
) -> None:
    """Locks what a structure edit writes besides its locked lot, before it
    writes anything, so the edit commits once and a lost race can run it
    again: the rows the reconciler derives from the lot, the production
    orders whose duration it snapshots again, the quote requests naming a
    position it deletes, and last the project's time budget lock. Every
    lifecycle row is held before the time budget lock, as that lock
    requires, and the time budget lock is held before the first step
    write, so the edit never waits for it while holding step rows another
    recompute writes."""
    reconciler.touch_lots([lot.id])
    await reconciler.lock_touched(
        also=AggregateIds.of({LifecycleAggregate.PRODUCTION_ORDERS: sorted(production_order_ids)})
    )
    await lock_quote_requests_of_positions(reconciler, lots, sorted(deleted_position_ids))
    if time_budgets:
        await lots.lock_time_budgets(lot.project_id)


class RegroupLotPositions:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        order_item_repo: IOrderItemRepository | None = None,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._lots = lot_repo
        self._order_items = order_item_repo
        self._uow = uow
        self._reconciler = reconciler
        self._recompute = recompute_schedule

    async def execute(
        self, actor: User, lot_id: int, cmd: RegroupLotPositionsCommand
    ) -> list[LotPositionResult]:
        lot = await locked_lot(self._reconciler, self._lots, lot_id)
        LotRules.assert_can_edit_structure(actor, lot)

        steps = await self._lots.get_steps(lot_id)
        validate_position_grouping(steps, cmd.groups)
        steps_by_id = {s.id: s for s in steps}

        old_positions = await self._lots.get_positions(lot_id)

        # A group identical to an existing position's step set preserves
        # that position; only positions whose membership actually changes
        # are torn down, and only THOSE must still be unassigned. Groups
        # are disjoint (validate_position_grouping), so each old position
        # can match at most one group and vice versa.
        step_ids_by_position: dict[int, set[int]] = {}
        for step in steps:
            step_ids_by_position.setdefault(step.position_id, set()).add(step.id)
        positions_by_step_ids = {
            frozenset(ids): position
            for position in old_positions
            if (ids := step_ids_by_position.get(position.id))
        }
        preserved_by_group_index = {
            index: position
            for index, group in enumerate(cmd.groups)
            if (position := positions_by_step_ids.get(frozenset(group)))
        }
        preserved_ids = {p.id for p in preserved_by_group_index.values()}
        removed_positions = [p for p in old_positions if p.id not in preserved_ids]
        LotRules.assert_positions_unassigned(removed_positions)
        now = now_utc()

        # All kept positions (preserved and new) are first parked on
        # temporary negative sequence numbers to avoid colliding with the
        # still-present old positions' sequences under the
        # UNIQUE(lot_id, sequence) constraint, real positions are always
        # sequence >= 1. Once the orphaned old positions are deleted, a
        # second pass renumbers to the final 1..N sequence.
        new_positions: list[LotPosition] = []
        for temp_sequence, group in enumerate(cmd.groups, start=1):
            preserved = preserved_by_group_index.get(temp_sequence - 1)
            if preserved is not None:
                preserved.sequence = -temp_sequence
                await self._lots.save_position(preserved)
                new_positions.append(preserved)
                continue
            position = LotPosition(
                id=0,
                created=now,
                changed=now,
                changes=append_changelog([], actor.full_name, "Position created (regrouped)."),
                sequence=-temp_sequence,
                kind=LotPositionKind.default(),
                status=LotPositionStatus.default(),
                quantity=lot.quantity,
                quantity_completed=0.0,
                note=None,
                creator_id=actor.id,
                lot_id=lot_id,
            )
            saved_position = await self._lots.save_position(position)
            self._reconciler.touch_positions([saved_position.id], created=True)
            new_positions.append(saved_position)
            for step_id in group:
                step = steps_by_id[step_id]
                step.position_id = saved_position.id
                await self._lots.save_step(step)

        await lock_quote_requests_of_positions(
            self._reconciler, self._lots, [p.id for p in removed_positions]
        )
        for old_position in removed_positions:
            if self._order_items is not None:
                blocking = await self._order_items.get_by_lot_position_id(old_position.id)
                if blocking is not None:
                    raise LotPositionInUseError(
                        f"Position #{old_position.id} is referenced by order item #{blocking.id}."
                    )
            await self._lots.delete_position(old_position)

        for sequence, saved_position in enumerate(new_positions, start=1):
            saved_position.sequence = sequence
            await self._lots.save_position(saved_position)

        await self._lots.record_event(
            build_lot_event(
                lot_id,
                actor,
                LotEventType.POSITIONS_REGROUPED,
                "lot",
                f"Positions regrouped into {len(cmd.groups)} group(s).",
            )
        )
        self._reconciler.touch_lots([lot_id])
        await self._reconciler.run(actor, now)
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="regrouping lot positions; the change itself is committed."
        )
        log.info(f"Regrouped positions of lot #{lot_id}.")
        return [LotPositionMapper.to_result(p) for p in await self._lots.get_positions(lot_id)]


class AppendLotPosition:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        fabrication_method_repo: IFabricationMethodQueries,
        inspection_method_repo: IInspectionMethodQueries,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._lots = lot_repo
        self._fabrication_methods = fabrication_method_repo
        self._inspection_methods = inspection_method_repo
        self._uow = uow
        self._reconciler = reconciler

    async def execute(
        self, actor: User, lot_id: int, cmd: AppendLotPositionCommand
    ) -> LotPositionResult:
        lot = await locked_lot(self._reconciler, self._lots, lot_id)
        LotRules.assert_can_append_position(actor, lot)

        for step_input in cmd.steps:
            assert_valid_step_role(
                step_input.role, step_input.fabrication_method_id, step_input.inspection_method_id
            )
        if len(cmd.steps) > 1 and any(
            step_input.role == StepRole.INSPECTION for step_input in cmd.steps
        ):
            raise LotPositionGroupingInvalidError(
                "An inspection step cannot share a position with any other step; "
                "append it on its own or leave it out of a mixed append."
            )
        # An inspection step inherits its method's default durations unless
        # the caller sent its own (see seed_inspection_estimates).
        methods_by_index: dict[int, InspectionMethod] = {}
        for index, step_input in enumerate(cmd.steps):
            if step_input.role == StepRole.FABRICATION:
                assert step_input.fabrication_method_id is not None  # assert_valid_step_role above
                method = await self._fabrication_methods.get_by_id(step_input.fabrication_method_id)
                if not method:
                    raise FabricationMethodNotFoundError(
                        f"Fabrication method #{step_input.fabrication_method_id} not found."
                    )
                if method.archived:
                    raise FabricationMethodArchivedError(
                        f"Fabrication method #{step_input.fabrication_method_id} is archived."
                    )
            else:
                assert step_input.inspection_method_id is not None  # assert_valid_step_role above
                inspection_method = await self._inspection_methods.get_by_id(
                    step_input.inspection_method_id
                )
                if not inspection_method:
                    raise InspectionMethodNotFoundError(
                        f"Inspection method #{step_input.inspection_method_id} not found."
                    )
                if inspection_method.archived:
                    raise InspectionMethodArchivedError(
                        f"Inspection method #{step_input.inspection_method_id} is archived."
                    )
                methods_by_index[index] = inspection_method

        next_sequence = max((p.sequence for p in lot.positions), default=0) + 1
        next_step_sequence = len(lot.steps) + 1
        now = now_utc()

        position = LotPosition(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Position appended."),
            sequence=next_sequence,
            kind=LotPositionKind.default(),
            status=LotPositionStatus.default(),
            quantity=lot.quantity,
            quantity_completed=0.0,
            note=None,
            creator_id=actor.id,
            lot_id=lot_id,
        )
        saved_position = await self._lots.save_position(position)
        self._reconciler.touch_positions([saved_position.id], created=True)

        for offset, step_input in enumerate(cmd.steps):
            method_for_step = methods_by_index.get(offset)
            setup_minutes, minutes_per_piece = (
                seed_inspection_estimates(
                    method_for_step,
                    step_input.estimated_setup_minutes,
                    step_input.estimated_minutes_per_piece,
                )
                if method_for_step is not None
                else (step_input.estimated_setup_minutes, step_input.estimated_minutes_per_piece)
            )
            step = LotStep(
                id=0,
                created=now,
                note=step_input.note,
                estimated_setup_minutes=setup_minutes,
                estimated_minutes_per_piece=minutes_per_piece,
                sequence=next_step_sequence + offset,
                creator_id=actor.id,
                fabrication_method_id=step_input.fabrication_method_id,
                lot_id=lot_id,
                position_id=saved_position.id,
                source_process_id=None,
                role=step_input.role,
                inspection_method_id=step_input.inspection_method_id,
            )
            await self._lots.save_step(step)

        await self._lots.record_event(
            build_lot_event(
                lot_id,
                actor,
                LotEventType.POSITION_APPENDED,
                "position",
                f"Position #{saved_position.id} appended with {len(cmd.steps)} step(s).",
                entity_id=saved_position.id,
            )
        )
        self._reconciler.touch_lots([lot_id])
        await self._reconciler.run(actor, now)
        await self._uow.commit()
        log.info(f"Appended a position to lot #{lot_id}.")
        refreshed = found_or_raise(
            await self._lots.get_position_by_id(saved_position.id),
            LotPositionNotFoundError,
            f"Position #{saved_position.id} not found after append.",
        )
        return LotPositionMapper.to_result(refreshed)
