"""Applies a lot's complete step and position structure in one transaction,
so the step editor's save is atomic instead of a series of calls that can
fail halfway.

It enforces the union of the single-operation rules, never bypasses them.
A position whose exact step set survives keeps its row, kind, orders and
order item link; other positions are created fresh and emptied ones are
deleted. A position that is assigned or has progress must survive, keeps its
place among the surviving positions and gets no new position before it,
since its input comes from the position before it.

The lot is locked through the request's lock plan before anything is read,
and the lifecycle reconciler runs before the structure commits, deriving the
new positions and the lot's status from them. The structure, the project's
time budgets and the duration snapshot of the queued and paused orders whose
steps or time budgets moved, in any lot of the project, commit once, after
lock_structure_edit locked every row the save writes and then the time
budget lock; the schedule walk runs after the commit.
"""

from datetime import datetime

from src.modules.catalogue.domain.errors import FabricationMethodArchivedError
from src.modules.catalogue.domain.errors import FabricationMethodNotFoundError
from src.modules.catalogue.domain.errors import InspectionMethodArchivedError
from src.modules.catalogue.domain.errors import InspectionMethodNotFoundError
from src.modules.catalogue.domain.policies.inspection_method_rules import seed_inspection_estimates
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.catalogue.ports.outbound.catalogue_queries import IFabricationMethodQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IInspectionMethodQueries
from src.modules.fulfillment.application.dto.production_lot_dto import LotPositionResult
from src.modules.fulfillment.application.dto.production_lot_dto import ReplaceLotStructureCommand
from src.modules.fulfillment.application.dto.production_lot_dto import ReplaceLotStructureStepInput
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotPositionMapper
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
from src.modules.fulfillment.domain.errors import LotPositionAlreadyAssignedError
from src.modules.fulfillment.domain.errors import LotPositionGroupingInvalidError
from src.modules.fulfillment.domain.errors import LotPositionInUseError
from src.modules.fulfillment.domain.errors import LotStepNotFoundError
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.services.lot_rules import assert_moved_positions_free
from src.modules.fulfillment.domain.services.lot_rules import assert_no_new_position_before_progress
from src.modules.fulfillment.domain.services.lot_rules import assert_valid_step_role
from src.modules.fulfillment.domain.services.lot_rules import has_progress
from src.modules.fulfillment.domain.services.lot_rules import moved_position_ids
from src.modules.fulfillment.domain.services.production_order_rules import (
    compute_estimated_duration_minutes,
)
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
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
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class ReplaceLotStructure:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        fabrication_method_repo: IFabricationMethodQueries,
        inspection_method_repo: IInspectionMethodQueries,
        project_repo: IProjectQueries | None = None,
        *,
        order_repo: IProductionOrderRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        order_item_repo: IOrderItemRepository | None = None,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._lots = lot_repo
        self._fabrication_methods = fabrication_method_repo
        self._inspection_methods = inspection_method_repo
        self._projects = project_repo
        self._orders = order_repo
        self._recompute = recompute_schedule
        self._order_items = order_item_repo
        self._uow = uow
        self._reconciler = reconciler

    async def execute(
        self, actor: User, lot_id: int, cmd: ReplaceLotStructureCommand
    ) -> list[LotPositionResult]:
        lot = await locked_lot(self._reconciler, self._lots, lot_id)
        LotRules.assert_can_edit_structure(actor, lot)

        current_steps = {s.id: s for s in await self._lots.get_steps(lot_id)}
        current_positions = await self._lots.get_positions(lot_id)
        submitted = [[step for step in position.steps] for position in cmd.positions]

        self._assert_valid_payload(lot_id, submitted, current_steps)
        await self._assert_methods_resolvable(submitted, current_steps)
        preserved_by_index = self._resolve_preserved_positions(submitted, current_positions)
        self._assert_assigned_positions_untouched(
            submitted, current_steps, current_positions, preserved_by_index
        )

        durations_changed = self._collect_positions_with_changed_durations(submitted, current_steps)
        preserved_ids = {p.id for p in preserved_by_index.values()}
        await lock_structure_edit(
            self._reconciler,
            self._lots,
            lot,
            production_order_ids=[
                *await self._order_ids_of(durations_changed),
                *await self._budget_order_ids(lot),
            ],
            deleted_position_ids=[p.id for p in current_positions if p.id not in preserved_ids],
            time_budgets=self._projects is not None,
        )
        await self._write(
            actor, lot, submitted, current_steps, current_positions, preserved_by_index
        )
        # Before the resnapshot, which reads the time budget.
        touched_machine_ids: set[int | None] = set()
        if self._projects is not None:
            touched_machine_ids = await recompute_project_time_budgets(
                lot.project_id,
                self._projects,
                self._lots,
                BudgetOrders(self._orders, self._reconciler.lock_plan),
            )
        touched_machine_ids |= await self._resnapshot_sibling_orders(durations_changed)
        await self._uow.commit()
        if touched_machine_ids:
            await recompute_schedule_after_commit(
                self._recompute,
                after="replacing a lot structure; the replacement itself is committed.",
            )

        log.info(f"Saved the step structure of lot #{lot_id}.")
        return [LotPositionMapper.to_result(p) for p in await self._lots.get_positions(lot_id)]

    # ── Validation ────────────────────────────────────────────────────

    def _assert_valid_payload(
        self,
        lot_id: int,
        submitted: list[list[ReplaceLotStructureStepInput]],
        current_steps: dict[int, LotStep],
    ) -> None:
        seen: set[int] = set()
        for group in submitted:
            for step in group:
                assert_valid_step_role(
                    step.role, step.fabrication_method_id, step.inspection_method_id
                )
                if step.id is None:
                    continue
                if step.id not in current_steps:
                    raise LotStepNotFoundError(f"Step #{step.id} does not belong to lot #{lot_id}.")
                if step.id in seen:
                    raise LotPositionGroupingInvalidError(
                        f"Step #{step.id} appears more than once in the submitted structure."
                    )
                seen.add(step.id)
                if step.role != current_steps[step.id].role:
                    raise LotPositionGroupingInvalidError(
                        f"Step #{step.id}'s role cannot be changed from "
                        f"{current_steps[step.id].role.value!r} to {step.role.value!r}; "
                        "delete and re-add instead."
                    )

            if len(group) > 1 and any(s.role == StepRole.INSPECTION for s in group):
                raise LotPositionGroupingInvalidError(
                    "An inspection step cannot share a position with any other step."
                )

    async def _assert_methods_resolvable(
        self,
        submitted: list[list[ReplaceLotStructureStepInput]],
        current_steps: dict[int, LotStep],
    ) -> None:
        """An archived method may stay on a step but never be newly chosen."""
        for group in submitted:
            for step in group:
                existing = current_steps.get(step.id) if step.id is not None else None
                if step.role == StepRole.FABRICATION:
                    await self._assert_fabrication_method_resolvable(step, existing)
                else:
                    await self._assert_inspection_method_resolvable(step, existing)

    async def _assert_fabrication_method_resolvable(
        self, step: ReplaceLotStructureStepInput, existing: LotStep | None
    ) -> None:
        assert step.fabrication_method_id is not None  # assert_valid_step_role
        method = await self._fabrication_methods.get_by_id(step.fabrication_method_id)
        if not method:
            raise FabricationMethodNotFoundError(
                f"Fabrication method #{step.fabrication_method_id} not found."
            )
        is_new_choice = (
            existing is None or existing.fabrication_method_id != step.fabrication_method_id
        )
        if method.archived and is_new_choice:
            raise FabricationMethodArchivedError(
                f"Fabrication method #{step.fabrication_method_id} is archived."
            )

    async def _assert_inspection_method_resolvable(
        self, step: ReplaceLotStructureStepInput, existing: LotStep | None
    ) -> None:
        assert step.inspection_method_id is not None  # assert_valid_step_role
        inspection_method = await self._inspection_methods.get_by_id(step.inspection_method_id)
        if not inspection_method:
            raise InspectionMethodNotFoundError(
                f"Inspection method #{step.inspection_method_id} not found."
            )
        is_new_choice = (
            existing is None or existing.inspection_method_id != step.inspection_method_id
        )
        if inspection_method.archived and is_new_choice:
            raise InspectionMethodArchivedError(
                f"Inspection method #{step.inspection_method_id} is archived."
            )

    def _resolve_preserved_positions(
        self,
        submitted: list[list[ReplaceLotStructureStepInput]],
        current_positions: list[LotPosition],
    ) -> dict[int, LotPosition]:
        """A group whose existing step ids exactly match a stored position
        keeps that position row."""
        by_step_ids = {
            frozenset(s.id for s in position.steps): position
            for position in current_positions
            if position.steps
        }
        preserved: dict[int, LotPosition] = {}
        for index, group in enumerate(submitted):
            if any(step.id is None for step in group):
                continue
            match = by_step_ids.get(frozenset(step.id for step in group if step.id is not None))
            if match is not None and match.id not in {p.id for p in preserved.values()}:
                preserved[index] = match
        return preserved

    def _assert_assigned_positions_untouched(
        self,
        submitted: list[list[ReplaceLotStructureStepInput]],
        current_steps: dict[int, LotStep],
        current_positions: list[LotPosition],
        preserved_by_index: dict[int, LotPosition],
    ) -> None:
        """A position that is assigned or has progress must survive whole
        with its fabrication methods unchanged, keep its place among the
        surviving positions and get no new position before it."""
        preserved_ids = {p.id for p in preserved_by_index.values()}
        committed = [
            p for p in current_positions if p.kind != LotPositionKind.UNASSIGNED or has_progress(p)
        ]
        for position in committed:
            if position.id not in preserved_ids:
                raise LotPositionAlreadyAssignedError(
                    f"Position #{position.id} is already assigned and its steps cannot be "
                    f"added to, removed, or regrouped."
                )

        in_order = sorted(current_positions, key=lambda p: p.sequence)
        assert_moved_positions_free(
            current_positions,
            moved_position_ids(
                [p.id for p in in_order],
                [preserved_by_index[i].id for i in sorted(preserved_by_index)],
            ),
        )
        assert_no_new_position_before_progress(
            [preserved_by_index.get(index) for index in range(len(submitted))]
        )

        submitted_by_id = {s.id: s for group in submitted for s in group if s.id is not None}
        for position in committed:
            for step in position.steps:
                incoming = submitted_by_id.get(step.id)
                if incoming is None:
                    continue
                if (
                    step.role == StepRole.FABRICATION
                    and incoming.fabrication_method_id != step.fabrication_method_id
                ):
                    raise LotPositionAlreadyAssignedError(
                        f"Step #{step.id} belongs to already-assigned position "
                        f"#{position.id}; its fabrication method cannot be changed."
                    )

    # ── Write ─────────────────────────────────────────────────────────

    async def _write(
        self,
        actor: User,
        lot: ProductionLot,
        submitted: list[list[ReplaceLotStructureStepInput]],
        current_steps: dict[int, LotStep],
        current_positions: list[LotPosition],
        preserved_by_index: dict[int, LotPosition],
    ) -> None:
        now = now_utc()
        kept_step_ids = {s.id for group in submitted for s in group if s.id is not None}
        removed_steps = [s for step_id, s in current_steps.items() if step_id not in kept_step_ids]
        preserved_ids = {p.id for p in preserved_by_index.values()}

        for step in removed_steps:
            await self._lots.delete_step(step)

        await self._park_on_negative_sequence(current_positions, current_steps, kept_step_ids)

        added = 0
        updated = 0
        step_sequence = 0
        for index, group in enumerate(submitted):
            position = await self._resolve_or_create_position(
                index, group, preserved_by_index, actor, lot, now
            )
            group_added, group_updated, step_sequence = await self._write_group_steps(
                group, position, current_steps, actor, lot, now, step_sequence
            )
            added += group_added
            updated += group_updated

        await self._delete_unpreserved_positions(current_positions, preserved_ids)

        await self._record_events(actor, lot.id, added, len(removed_steps), updated)
        self._reconciler.touch_lots([lot.id])
        await self._reconciler.run(actor, now)

    async def _park_on_negative_sequence(
        self,
        current_positions: list[LotPosition],
        current_steps: dict[int, LotStep],
        kept_step_ids: set[int],
    ) -> None:
        """Parks positions and steps on negative sequences first, because the
        unique sequence constraints are not deferrable."""
        for offset, position in enumerate(current_positions, start=1):
            position.sequence = -offset
            await self._lots.save_position(position)
        for offset, step in enumerate(current_steps.values(), start=1):
            if step.id in kept_step_ids:
                step.sequence = -offset
                await self._lots.save_step(step)

    async def _resolve_or_create_position(
        self,
        index: int,
        group: list[ReplaceLotStructureStepInput],
        preserved_by_index: dict[int, LotPosition],
        actor: User,
        lot: ProductionLot,
        now: datetime,
    ) -> LotPosition:
        """A preserved group keeps its stored position row, renumbered in
        place; any other group gets a fresh, UNASSIGNED one."""
        preserved = preserved_by_index.get(index)
        if preserved is not None:
            preserved.sequence = index + 1
            preserved.changed = now
            return await self._lots.save_position(preserved)
        created = await self._lots.save_position(
            LotPosition(
                id=0,
                created=now,
                changed=now,
                changes=append_changelog(
                    [], actor.full_name, "Position created (structure saved)."
                ),
                sequence=index + 1,
                kind=LotPositionKind.default(),
                status=LotPositionStatus.default(),
                quantity=lot.quantity,
                quantity_completed=0.0,
                note=None,
                creator_id=actor.id,
                lot_id=lot.id,
            )
        )
        self._reconciler.touch_positions([created.id], created=True)
        return created

    async def _write_group_steps(
        self,
        group: list[ReplaceLotStructureStepInput],
        position: LotPosition,
        current_steps: dict[int, LotStep],
        actor: User,
        lot: ProductionLot,
        now: datetime,
        step_sequence: int,
    ) -> tuple[int, int, int]:
        """Writes every step of one submitted group onto `position`, in
        order. Returns (added, updated, next_step_sequence) so the caller
        can keep a running total/cursor across groups."""
        added = 0
        updated = 0
        for step_input in group:
            step_sequence += 1
            if step_input.id is None:
                await self._lots.save_step(
                    await self._build_step(actor, lot, position, step_input, step_sequence, now)
                )
                added += 1
            else:
                step = current_steps[step_input.id]
                if self._apply_step_fields(step, step_input):
                    updated += 1
                step.position_id = position.id
                step.sequence = step_sequence
                await self._lots.save_step(step)
        return added, updated, step_sequence

    async def _delete_unpreserved_positions(
        self, current_positions: list[LotPosition], preserved_ids: set[int]
    ) -> None:
        """Deletes positions that did not survive, refusing one still
        referenced by an order item. The quote requests naming them are
        locked up front (lock_structure_edit)."""
        for position in current_positions:
            if position.id in preserved_ids:
                continue
            if self._order_items is not None:
                blocking = await self._order_items.get_by_lot_position_id(position.id)
                if blocking is not None:
                    raise LotPositionInUseError(
                        f"Position #{position.id} is referenced by order item #{blocking.id}."
                    )
            await self._lots.delete_position(position)

    async def _build_step(
        self,
        actor: User,
        lot: ProductionLot,
        position: LotPosition,
        step_input: ReplaceLotStructureStepInput,
        sequence: int,
        now: datetime,
    ) -> LotStep:
        setup_minutes = step_input.estimated_setup_minutes
        minutes_per_piece = step_input.estimated_minutes_per_piece
        if step_input.role == StepRole.INSPECTION:
            assert step_input.inspection_method_id is not None  # assert_valid_step_role
            method = await self._inspection_methods.get_by_id(step_input.inspection_method_id)
            assert method is not None  # _assert_methods_resolvable
            # Inherits the method's default durations unless given.
            setup_minutes, minutes_per_piece = seed_inspection_estimates(
                method, setup_minutes, minutes_per_piece
            )
        return LotStep(
            id=0,
            created=now,
            note=step_input.note,
            estimated_setup_minutes=setup_minutes,
            estimated_minutes_per_piece=minutes_per_piece,
            sequence=sequence,
            creator_id=actor.id,
            fabrication_method_id=step_input.fabrication_method_id,
            lot_id=lot.id,
            position_id=position.id,
            source_process_id=None,
            role=step_input.role,
            inspection_method_id=step_input.inspection_method_id,
        )

    @staticmethod
    def _apply_step_fields(step: LotStep, step_input: ReplaceLotStructureStepInput) -> bool:
        """Copies the editable fields onto an existing step, reporting
        whether any of them actually changed (for the audit trail)."""
        changed = (
            step.fabrication_method_id != step_input.fabrication_method_id
            or step.inspection_method_id != step_input.inspection_method_id
            or step.note != step_input.note
            or step.estimated_setup_minutes != step_input.estimated_setup_minutes
            or step.estimated_minutes_per_piece != step_input.estimated_minutes_per_piece
        )
        step.fabrication_method_id = step_input.fabrication_method_id
        step.inspection_method_id = step_input.inspection_method_id
        step.note = step_input.note
        step.estimated_setup_minutes = step_input.estimated_setup_minutes
        step.estimated_minutes_per_piece = step_input.estimated_minutes_per_piece
        return changed

    async def _record_events(
        self, actor: User, lot_id: int, added: int, removed: int, updated: int
    ) -> None:
        summary = f"Step structure saved ({added} added, {removed} removed, {updated} updated)."
        await self._lots.record_event(
            build_lot_event(lot_id, actor, LotEventType.POSITIONS_REGROUPED, "lot", summary)
        )

    # ── Schedule follow-up ────────────────────────────────────────────

    def _collect_positions_with_changed_durations(
        self,
        submitted: list[list[ReplaceLotStructureStepInput]],
        current_steps: dict[int, LotStep],
    ) -> set[int]:
        """Positions whose duration inputs moved, resolved BEFORE the write
        while the stored values are still readable."""
        touched: set[int] = set()
        for group in submitted:
            for step_input in group:
                if step_input.id is None:
                    continue
                step = current_steps[step_input.id]
                if (
                    step.estimated_setup_minutes != step_input.estimated_setup_minutes
                    or step.estimated_minutes_per_piece != step_input.estimated_minutes_per_piece
                ):
                    touched.add(step.position_id)
        return touched

    async def _order_ids_of(self, position_ids: set[int]) -> list[int]:
        """The production orders of the positions whose duration inputs
        moved, which the save locks before it writes."""
        if not position_ids:
            return []
        return [
            order.id
            for position_id in sorted(position_ids)
            for order in await self._orders.get_by_lot_position_id(position_id)
        ]

    async def _budget_order_ids(self, lot: ProductionLot) -> list[int]:
        """The queued and paused orders of the lot's project, whose duration
        the time budget recompute may snapshot again, which the save locks
        before it writes; none when it recomputes no budget."""
        if self._projects is None:
            return []
        locks = await budget_order_locks([lot.project_id], self._lots, self._orders)
        return sorted(locks.get(LifecycleAggregate.PRODUCTION_ORDERS))

    async def _resnapshot_sibling_orders(self, position_ids: set[int]) -> set[int | None]:
        """Copies edited estimates onto queued and paused orders, which
        snapshot their duration at creation, reading them under the locks
        the save took. Returns the touched machine ids."""
        touched_machine_ids: set[int | None] = set()
        if not position_ids:
            return touched_machine_ids
        for position_id in sorted(position_ids):
            position = await self._lots.get_position_by_id(position_id)
            if position is None:
                continue
            for order in await self._orders.get_by_lot_position_id(position_id):
                if order.status not in (
                    ProductionOrderStatus.QUEUED,
                    ProductionOrderStatus.PAUSED,
                ):
                    continue
                order.estimated_duration_minutes = compute_estimated_duration_minutes(
                    position.steps, order.quantity
                )
                await self._orders.save(order)
                touched_machine_ids.add(order.machine_id)
        return touched_machine_ids
