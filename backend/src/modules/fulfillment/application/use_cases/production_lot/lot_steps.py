"""Structural operations on a lot's steps at any non-terminal status: add,
update, delete and reorder.

Add and delete never touch an assigned position. A step is added after the
last step of its position, so each position's steps stay one run. A delete
that empties a position removes it and renumbers the positions after it.
Reorder moves a position only while it is unassigned and has no progress,
because a committed position's input comes from the position before it. On
update, only a fabrication method change is guarded, since it can
invalidate the chosen machine; estimate edits resnapshot queued and paused
orders and trigger a recompute.

Add, delete and reorder lock the lot through the request's lock plan before
they read what they check, and run the lifecycle reconciler before they
commit, because they change which positions the lot has or in what order:
deleting the last open position, for one, completes the lot. Update records
no lifecycle fact.

Add, update and delete commit once: the step writes, the project's time
budgets and the duration snapshot of the queued and paused orders whose
steps or time budgets moved, in any lot of the project, go into one
transaction, so a lost race leaves nothing committed and the request can run
again. The rows they write are locked first and the time budget lock after
them, before any step is written (lock_structure_edit). The schedule walk
runs after the commit.
"""

from src.modules.catalogue.domain.errors import FabricationMethodArchivedError
from src.modules.catalogue.domain.errors import FabricationMethodNotFoundError
from src.modules.catalogue.domain.errors import InspectionMethodArchivedError
from src.modules.catalogue.domain.errors import InspectionMethodNotFoundError
from src.modules.catalogue.domain.policies.inspection_method_rules import seed_inspection_estimates
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.catalogue.ports.outbound.catalogue_queries import IFabricationMethodQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IInspectionMethodQueries
from src.modules.fulfillment.application.dto.production_lot_dto import AddLotStepCommand
from src.modules.fulfillment.application.dto.production_lot_dto import LotStepResult
from src.modules.fulfillment.application.dto.production_lot_dto import ReorderLotStepsCommand
from src.modules.fulfillment.application.dto.production_lot_dto import UpdateLotStepCommand
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotStepMapper
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.time_budget_propagation import BudgetOrders
from src.modules.fulfillment.application.services.time_budget_propagation import budget_order_locks
from src.modules.fulfillment.application.services.time_budget_propagation import (
    recompute_project_time_budgets,
)
from src.modules.fulfillment.application.use_cases.production_lot.lot_positions import (
    lock_structure_edit,
)
from src.modules.fulfillment.application.use_cases.production_lot.lot_positions import locked_lot
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.domain.errors import LotPositionGroupingInvalidError
from src.modules.fulfillment.domain.errors import LotPositionInUseError
from src.modules.fulfillment.domain.errors import LotPositionNotFoundError
from src.modules.fulfillment.domain.errors import LotStepNotFoundError
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.services.lot_rules import assert_moved_positions_free
from src.modules.fulfillment.domain.services.lot_rules import assert_valid_step_role
from src.modules.fulfillment.domain.services.lot_rules import moved_position_ids
from src.modules.fulfillment.domain.services.production_order_rules import (
    compute_estimated_duration_minutes,
)
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


def _assert_reorder_keeps_positions_contiguous(
    ordered_step_ids: list[int], by_id: dict[int, LotStep]
) -> None:
    """A reorder keeps position membership, so each position's steps must
    stay one unbroken run."""
    seen_positions: set[int] = set()
    last_position_id: int | None = None
    for step_id in ordered_step_ids:
        position_id = by_id[step_id].position_id
        if position_id != last_position_id:
            if position_id in seen_positions:
                raise LotPositionGroupingInvalidError(
                    f"Reordering must keep each position's steps contiguous "
                    f"(position #{position_id} would be split)."
                )
            seen_positions.add(position_id)
            last_position_id = position_id


def _step_of_lot(step: LotStep | None, step_id: int, lot_id: int | None) -> LotStep:
    """The step, refused as not found when it is missing or belongs to
    another lot than the one named."""
    if step is None or (lot_id is not None and step.lot_id != lot_id):
        raise LotStepNotFoundError(f"Step #{step_id} not found.")
    return step


async def _budget_order_ids(
    projects: IProjectQueries | None,
    lots: IProductionLotRepository,
    orders: IProductionOrderRepository,
    lot: ProductionLot,
) -> list[int]:
    """The queued and paused orders of the lot's project, which the time
    budget recompute may snapshot again, so the edit locks them with its
    other rows; none when the edit recomputes no budget."""
    if projects is None:
        return []
    locks = await budget_order_locks([lot.project_id], lots, orders)
    return sorted(locks.get(LifecycleAggregate.PRODUCTION_ORDERS))


class AddLotStep:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        fabrication_method_repo: IFabricationMethodQueries,
        inspection_method_repo: IInspectionMethodQueries,
        project_repo: IProjectQueries | None = None,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        order_repo: IProductionOrderRepository,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        """The production orders are the queued and paused ones of the
        project, whose duration the time budget recompute snapshots again;
        the schedule walk runs after the commit when one changed."""
        self._lots = lot_repo
        self._fabrication_methods = fabrication_method_repo
        self._inspection_methods = inspection_method_repo
        self._projects = project_repo
        self._uow = uow
        self._reconciler = reconciler
        self._orders = order_repo
        self._recompute = recompute_schedule

    async def execute(self, actor: User, lot_id: int, cmd: AddLotStepCommand) -> LotStepResult:
        lot = await locked_lot(self._reconciler, self._lots, lot_id)
        LotRules.assert_can_edit_structure(actor, lot)

        position = await self._lots.get_position_by_id(cmd.position_id)
        if not position or position.lot_id != lot_id:
            raise LotPositionNotFoundError(
                f"Position #{cmd.position_id} not found on lot #{lot_id}."
            )
        LotRules.assert_positions_unassigned([position])
        assert_valid_step_role(cmd.role, cmd.fabrication_method_id, cmd.inspection_method_id)
        if cmd.role == StepRole.INSPECTION and position.steps:
            # An inspection step needs a position of its own.
            raise LotPositionGroupingInvalidError(
                f"Position #{cmd.position_id} already has step(s); an inspection step "
                "must be its own position, added via append-position instead."
            )

        setup_minutes = cmd.estimated_setup_minutes
        minutes_per_piece = cmd.estimated_minutes_per_piece
        if cmd.role == StepRole.FABRICATION:
            assert cmd.fabrication_method_id is not None  # guaranteed by assert_valid_step_role
            method = await self._fabrication_methods.get_by_id(cmd.fabrication_method_id)
            if not method:
                raise FabricationMethodNotFoundError(
                    f"Fabrication method #{cmd.fabrication_method_id} not found."
                )
            if method.archived:
                raise FabricationMethodArchivedError(
                    f"Fabrication method #{cmd.fabrication_method_id} is archived."
                )
        else:
            assert cmd.inspection_method_id is not None  # guaranteed by assert_valid_step_role
            inspection_method = await self._inspection_methods.get_by_id(cmd.inspection_method_id)
            if not inspection_method:
                raise InspectionMethodNotFoundError(
                    f"Inspection method #{cmd.inspection_method_id} not found."
                )
            if inspection_method.archived:
                raise InspectionMethodArchivedError(
                    f"Inspection method #{cmd.inspection_method_id} is archived."
                )
            # An inspection step inherits its method's default durations
            # unless the caller sent its own.
            setup_minutes, minutes_per_piece = seed_inspection_estimates(
                inspection_method, setup_minutes, minutes_per_piece
            )

        await lock_structure_edit(
            self._reconciler,
            self._lots,
            lot,
            production_order_ids=await _budget_order_ids(
                self._projects, self._lots, self._orders, lot
            ),
            time_budgets=self._projects is not None,
        )
        now = now_utc()
        steps = await self._lots.get_steps(lot_id)
        step = LotStep(
            id=0,
            created=now,
            note=cmd.note,
            estimated_setup_minutes=setup_minutes,
            estimated_minutes_per_piece=minutes_per_piece,
            sequence=max((s.sequence for s in steps), default=0) + 1,
            creator_id=actor.id,
            fabrication_method_id=cmd.fabrication_method_id,
            lot_id=lot_id,
            position_id=cmd.position_id,
            source_process_id=None,
            role=cmd.role,
            inspection_method_id=cmd.inspection_method_id,
        )
        saved = await self._lots.save_step(step)
        # Saved last, then moved right after its position's last step.
        in_order = _with_step_after_its_position(steps, saved)
        if in_order != [*(s.id for s in steps), saved.id]:
            await self._lots.reorder_steps(lot_id, in_order)
            saved = await self._lots.get_step_by_id(saved.id) or saved
        await self._lots.record_event(
            build_lot_event(
                lot_id,
                actor,
                LotEventType.STEP_ADDED,
                "step",
                f"Step added to position #{cmd.position_id}.",
                entity_id=saved.id,
            )
        )
        self._reconciler.touch_lots([lot_id])
        await self._reconciler.run(actor, now)
        touched_machine_ids: set[int | None] = set()
        if self._projects is not None:
            touched_machine_ids = await recompute_project_time_budgets(
                lot.project_id,
                self._projects,
                self._lots,
                BudgetOrders(self._orders, self._reconciler.lock_plan),
            )
        await self._uow.commit()
        if touched_machine_ids:
            await recompute_schedule_after_commit(
                self._recompute, after="adding a lot step; the step itself is committed."
            )
        log.info(f"Added step #{saved.id} to lot #{lot_id}.")
        return LotStepMapper.to_result(saved)


def _with_step_after_its_position(steps: list[LotStep], added: LotStep) -> list[int]:
    """The step ids in sequence order with `added` right after the last
    step of its position, or last when the position has no other step."""
    ordered = sorted(steps, key=lambda s: s.sequence)
    last_of_position = max(
        (index for index, s in enumerate(ordered) if s.position_id == added.position_id),
        default=len(ordered) - 1,
    )
    ids = [s.id for s in ordered]
    return [*ids[: last_of_position + 1], added.id, *ids[last_of_position + 1 :]]


class UpdateLotStep:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        fabrication_method_repo: IFabricationMethodQueries,
        inspection_method_repo: IInspectionMethodQueries,
        project_repo: IProjectQueries | None = None,
        *,
        order_repo: IProductionOrderRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        uow: IUnitOfWork,
        lock_plan: LockPlan,
    ) -> None:
        self._lots = lot_repo
        self._fabrication_methods = fabrication_method_repo
        self._inspection_methods = inspection_method_repo
        self._projects = project_repo
        self._orders = order_repo
        self._recompute = recompute_schedule
        self._uow = uow
        self._lock_plan = lock_plan

    async def execute(
        self, actor: User, step_id: int, cmd: UpdateLotStepCommand, *, lot_id: int | None = None
    ) -> LotStepResult:
        """`lot_id`, as the route names it, must be the step's lot."""
        step = _step_of_lot(await self._lots.get_step_by_id(step_id), step_id, lot_id)
        # The lot is locked before the step and the lot are read for the
        # structure checks, as for every structure edit.
        await self._lock_plan.acquire(AggregateIds.of({LifecycleAggregate.LOTS: [step.lot_id]}))
        step = found_or_raise(
            await self._lots.get_step_by_id(step_id),
            LotStepNotFoundError,
            f"Step #{step_id} not found.",
        )
        lot = found_or_raise(
            await self._lots.get_by_id(step.lot_id),
            LotNotFoundError,
            f"Lot #{step.lot_id} not found.",
        )
        LotRules.assert_can_edit_structure(actor, lot)
        assert_valid_step_role(cmd.role, cmd.fabrication_method_id, cmd.inspection_method_id)
        if cmd.role != step.role:
            raise LotPositionGroupingInvalidError(
                f"Step #{step_id}'s role cannot be changed from {step.role.value!r} to "
                f"{cmd.role.value!r}; delete and re-add instead."
            )

        position = await self._lots.get_position_by_id(step.position_id)
        await self._validate_method_change(step, position, cmd)

        duration_inputs_changed = (
            cmd.estimated_setup_minutes != step.estimated_setup_minutes
            or cmd.estimated_minutes_per_piece != step.estimated_minutes_per_piece
        )

        await self._lock_for_write(lot, position, duration_inputs_changed)
        step.fabrication_method_id = cmd.fabrication_method_id
        step.inspection_method_id = cmd.inspection_method_id
        step.note = cmd.note
        step.estimated_setup_minutes = cmd.estimated_setup_minutes
        step.estimated_minutes_per_piece = cmd.estimated_minutes_per_piece

        saved = await self._lots.save_step(step)
        await self._lots.record_event(
            build_lot_event(
                lot.id,
                actor,
                LotEventType.STEP_UPDATED,
                "step",
                f"Step #{step_id} updated.",
                entity_id=step_id,
            )
        )
        # Before the resnapshot, which reads the time budget.
        touched_machine_ids: set[int | None] = set()
        if self._projects is not None:
            touched_machine_ids = await recompute_project_time_budgets(
                lot.project_id,
                self._projects,
                self._lots,
                BudgetOrders(self._orders, self._lock_plan),
            )
        touched_machine_ids |= await self._resnapshot_sibling_orders(
            position, duration_inputs_changed
        )
        await self._uow.commit()

        if touched_machine_ids:
            await recompute_schedule_after_commit(
                self._recompute,
                after=f"updating step #{step_id}; the update itself is committed.",
            )

        log.info(f"Updated step #{step_id}.")
        return LotStepMapper.to_result(saved)

    async def _validate_method_change(
        self, step: LotStep, position: LotPosition | None, cmd: UpdateLotStepCommand
    ) -> bool:
        """Validates the target method and returns whether it changes.

        Only a fabrication method change on an assigned position is refused,
        because it can break the machine's capability match. An inspection
        method is always changeable: QA machines are not matched per method,
        and the position is born INTERNAL, so a gate would lock it forever.
        An archived method is only rejected when newly chosen."""
        changing_method = (
            cmd.fabrication_method_id != step.fabrication_method_id
            or cmd.inspection_method_id != step.inspection_method_id
        )
        if position and changing_method and step.role == StepRole.FABRICATION:
            LotRules.assert_positions_unassigned([position])

        if cmd.role == StepRole.FABRICATION:
            assert cmd.fabrication_method_id is not None  # guaranteed by assert_valid_step_role
            method = await self._fabrication_methods.get_by_id(cmd.fabrication_method_id)
            if not method:
                raise FabricationMethodNotFoundError(
                    f"Fabrication method #{cmd.fabrication_method_id} not found."
                )
            if changing_method and method.archived:
                raise FabricationMethodArchivedError(
                    f"Fabrication method #{cmd.fabrication_method_id} is archived."
                )
        else:
            assert cmd.inspection_method_id is not None  # guaranteed by assert_valid_step_role
            inspection_method = await self._inspection_methods.get_by_id(cmd.inspection_method_id)
            if not inspection_method:
                raise InspectionMethodNotFoundError(
                    f"Inspection method #{cmd.inspection_method_id} not found."
                )
            if changing_method and inspection_method.archived:
                raise InspectionMethodArchivedError(
                    f"Inspection method #{cmd.inspection_method_id} is archived."
                )
        return changing_method

    async def _lock_for_write(
        self, lot: ProductionLot, position: LotPosition | None, duration_inputs_changed: bool
    ) -> None:
        """Locks the production orders whose duration the edit snapshots
        again, after the lot: the position's own and the queued and paused
        orders of the project, for the time budget recompute. Then it takes
        the project's time budget lock, both before the step is written, so
        the edit commits once; see lock_structure_edit."""
        order_ids = await _budget_order_ids(self._projects, self._lots, self._orders, lot)
        if duration_inputs_changed and position is not None:
            order_ids += [o.id for o in await self._orders.get_by_lot_position_id(position.id)]
        await self._lock_plan.acquire(
            AggregateIds.of({LifecycleAggregate.PRODUCTION_ORDERS: order_ids})
        )
        if self._projects is not None:
            await self._lots.lock_time_budgets(lot.project_id)

    async def _resnapshot_sibling_orders(
        self, position: LotPosition | None, duration_inputs_changed: bool
    ) -> set[int | None]:
        """Orders snapshot their duration at creation, so an estimate edit
        is copied onto queued and paused orders, read under the locks
        _lock_for_write took. Returns the touched machine ids."""
        touched_machine_ids: set[int | None] = set()
        if not (duration_inputs_changed and position):
            return touched_machine_ids
        fresh_position = await self._lots.get_position_by_id(position.id)
        sibling_orders = (
            await self._orders.get_by_lot_position_id(position.id) if fresh_position else []
        )
        for order in sibling_orders:
            if order.status not in (
                ProductionOrderStatus.QUEUED,
                ProductionOrderStatus.PAUSED,
            ):
                continue
            order.estimated_duration_minutes = compute_estimated_duration_minutes(
                fresh_position.steps if fresh_position else [], order.quantity
            )
            await self._orders.save(order)
            touched_machine_ids.add(order.machine_id)
        return touched_machine_ids


class DeleteLotStep:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        project_repo: IProjectQueries | None = None,
        order_item_repo: IOrderItemRepository | None = None,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        order_repo: IProductionOrderRepository,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        """The production orders are the queued and paused ones of the
        project, whose duration the time budget recompute snapshots again."""
        self._lots = lot_repo
        self._projects = project_repo
        self._orders = order_repo
        self._order_items = order_item_repo
        self._uow = uow
        self._reconciler = reconciler
        self._recompute = recompute_schedule

    async def execute(self, actor: User, step_id: int, *, lot_id: int | None = None) -> None:
        """`lot_id`, as the route names it, must be the step's lot."""
        found = _step_of_lot(await self._lots.get_step_by_id(step_id), step_id, lot_id)
        lot = await locked_lot(self._reconciler, self._lots, found.lot_id)
        LotRules.assert_can_edit_structure(actor, lot)
        step = found_or_raise(
            await self._lots.get_step_by_id(step_id),
            LotStepNotFoundError,
            f"Step #{step_id} not found.",
        )
        position = await self._lots.get_position_by_id(step.position_id)
        if position:
            LotRules.assert_positions_unassigned([position])

        lot_id = step.lot_id
        position_id = step.position_id
        # A position left without steps is removed with its last step, so an
        # order item still pointing at it rejects the whole delete up front.
        empties_position = not [
            s
            for s in await self._lots.get_steps(lot_id)
            if s.position_id == position_id and s.id != step_id
        ]
        if empties_position and position and self._order_items is not None:
            blocking = await self._order_items.get_by_lot_position_id(position.id)
            if blocking is not None:
                raise LotPositionInUseError(
                    f"Position #{position.id} is referenced by order item #{blocking.id}."
                )

        await lock_structure_edit(
            self._reconciler,
            self._lots,
            lot,
            production_order_ids=await _budget_order_ids(
                self._projects, self._lots, self._orders, lot
            ),
            deleted_position_ids=[position.id] if empties_position and position else [],
            time_budgets=self._projects is not None,
        )
        await self._lots.delete_step(step)
        await self._lots.record_event(
            build_lot_event(
                lot_id,
                actor,
                LotEventType.STEP_DELETED,
                "step",
                f"Step #{step_id} deleted.",
                entity_id=step_id,
            )
        )
        if empties_position and position:
            await self._lots.delete_position(position)
            # Close the gap in the position sequence too.
            remaining_positions = [p.id for p in await self._lots.get_positions(lot_id)]
            if remaining_positions:
                await self._lots.reorder_positions(lot_id, remaining_positions)

        # Re-sequence remaining steps to close the gap left by the delete.
        remaining_ids = [s.id for s in await self._lots.get_steps(lot_id)]
        if remaining_ids:
            await self._lots.reorder_steps(lot_id, remaining_ids)

        self._reconciler.touch_lots([lot_id])
        await self._reconciler.run(actor, now_utc())
        if self._projects is not None:
            await recompute_project_time_budgets(
                lot.project_id,
                self._projects,
                self._lots,
                BudgetOrders(self._orders, self._reconciler.lock_plan),
            )
        await self._uow.commit()
        # A removed position unblocks or reblocks the later steps' dates.
        await recompute_schedule_after_commit(
            self._recompute, after="deleting a lot step; the change itself is committed."
        )

        log.info(f"Deleted step #{step_id} from lot #{lot_id}.")


class ReorderLotSteps:
    """Reorders a lot's steps and renumbers its positions to match.

    Steps keep their positions, so each position must stay contiguous and
    the step order determines the position order. Position sequence drives
    the production chain, so it is rewritten too. A position that is
    assigned or has progress keeps its place among the other positions,
    since its input comes from the one before it."""

    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        self._lots = lot_repo
        self._uow = uow
        self._reconciler = reconciler
        self._recompute = recompute_schedule

    async def execute(
        self, actor: User, lot_id: int, cmd: ReorderLotStepsCommand
    ) -> list[LotStepResult]:
        lot = await locked_lot(self._reconciler, self._lots, lot_id)
        LotRules.assert_can_edit_structure(actor, lot, LifecycleAction.REORDER_POSITIONS)

        current = await self._lots.get_steps(lot_id)
        current_ids = {s.id for s in current}
        given_ids = set(cmd.ordered_step_ids)
        if current_ids != given_ids or len(cmd.ordered_step_ids) != len(current):
            raise LotPositionGroupingInvalidError(
                f"Reorder list for lot #{lot_id} must contain exactly its current "
                f"step IDs {sorted(current_ids)}, got {cmd.ordered_step_ids!r}."
            )

        by_id = {s.id: s for s in current}
        _assert_reorder_keeps_positions_contiguous(cmd.ordered_step_ids, by_id)

        # Positions are contiguous in the new step order (asserted above),
        # so first-appearance order IS the new position order.
        ordered_position_ids: list[int] = []
        for step_id in cmd.ordered_step_ids:
            position_id = by_id[step_id].position_id
            if position_id not in ordered_position_ids:
                ordered_position_ids.append(position_id)
        positions = await self._lots.get_positions(lot_id)
        current_position_ids = [p.id for p in positions]
        assert_moved_positions_free(
            positions, moved_position_ids(current_position_ids, ordered_position_ids)
        )

        reordered = await self._lots.reorder_steps(lot_id, cmd.ordered_step_ids)
        if ordered_position_ids != current_position_ids:
            await self._lots.reorder_positions(lot_id, ordered_position_ids)

        await self._lots.record_event(
            build_lot_event(lot_id, actor, LotEventType.STEPS_REORDERED, "lot", "Steps reordered.")
        )
        self._reconciler.touch_lots([lot_id])
        await self._reconciler.run(actor, now_utc())
        await self._uow.commit()
        await recompute_schedule_after_commit(
            self._recompute, after="reordering lot steps; the change itself is committed."
        )
        log.info(f"Reordered steps of lot #{lot_id}.")
        return [LotStepMapper.to_result(s) for s in reordered]
