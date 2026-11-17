"""Records a partial or final completion.

The order counts accepted pieces only, but its cap counts accepted plus
rejected. The completion row is the fact; the lifecycle reconciler derives
the order's status from the rows and stamps actual_end when they reach the
order's quantity, and derives the position's completed count, which sums
all its orders, and the statuses of the position and the lot. The accepted
pieces are checked against what the upstream made available before
anything is written. An inspection completion needs WRITE_INSPECTIONS and,
when the method requires evidence, an uploaded measurement report; its
rejected pieces go through the shared disposition before the reconciler
runs. Only an inspection may reject pieces. The reconciler derives the made
demands of the lot with the lot.

The lot and then the order are locked before the processed total is read,
so concurrent completions and scraps on one lot serialize and the cap and
the checks are computed from committed values. A completion that rejects
pieces also locks the lot's production orders and order lines, which its
disposition may cut.
"""

from datetime import datetime

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.production_order_dto import CreatedLotResult
from src.modules.fulfillment.application.dto.production_order_dto import ProductionOrderResult
from src.modules.fulfillment.application.dto.production_order_dto import (
    RecordProductionOrderCompletionCommand,
)
from src.modules.fulfillment.application.mappers.production_order_mapper import (
    ProductionOrderMapper,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.piece_disposition import DispositionOutcome
from src.modules.fulfillment.application.services.piece_disposition import DispositionRepositories
from src.modules.fulfillment.application.services.piece_disposition import apply_disposition
from src.modules.fulfillment.application.services.time_budget_propagation import BudgetOrders
from src.modules.fulfillment.application.services.time_budget_propagation import (
    recompute_time_budgets_of_projects,
)
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.application.use_cases.production_order._locks import lock_lot_and_order
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.errors import LotPositionNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderMeasurementEvidenceRequiredError
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.domain.events.production_order_events import (
    ProductionOrderCompletionRecorded,
)
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.lot_rules import assert_completion_within_available
from src.modules.fulfillment.domain.services.lot_rules import assert_disposition_keeps_completed
from src.modules.fulfillment.domain.services.production_order_rules import ProductionOrderRules
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_completion_date_allowed,
)
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_order_completion_within_order_quantity,
)
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_production_order_action,
)
from src.modules.fulfillment.domain.services.production_order_rules import assert_valid_disposition
from src.modules.fulfillment.domain.services.production_order_rules import assert_whole_completion
from src.modules.fulfillment.domain.services.production_order_rules import production_order_context
from src.modules.fulfillment.domain.services.production_order_rules import resolve_completion_split
from src.modules.fulfillment.domain.services.production_order_rules import resolve_operator_id
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_order_file_category import (
    ProductionOrderFileCategory,
)
from src.modules.fulfillment.domain.value_objects.scrap_reason import ScrapReason
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
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
from src.modules.fulfillment.ports.outbound.repositories.production_order_file_repository import (
    IProductionOrderFileRepository,
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
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.label_languages import resolve_label
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.events.base import DomainEvent
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


class RecordProductionOrderCompletion:
    def __init__(
        self,
        order_repo: IProductionOrderRepository,
        lot_repo: IProductionLotRepository,
        file_repo: IProductionOrderFileRepository | None = None,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        made_item_demand_repo: IMadeItemDemandItemRepository,
        made_item_allocation_repo: IMadeItemAllocationRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        create_lot: CreateLot,
        order_item_repo: IOrderItemRepository,
        parent_order_repo: IOrderRepository,
        interruption_repo: IProductionOrderInterruptionRepository,
        source_item_demand_repo: ISourceItemDemandRepository,
        source_item_allocation_repo: ISourceItemAllocationRepository,
        settings_repo: IFulfillmentSettingsRepository,
        bought_allocation_repo: IBoughtItemAllocationRepository,
        project_repo: IProjectQueries | None = None,
    ) -> None:
        """The order line, order, interruption, source demand, source
        allocation and bought allocation repositories are what a disposition
        of rejected pieces writes, the last one to settle the raw material
        demand of a lot it empties. The settings give the tenant's timezone
        the completion date is checked in. The projects
        give the time budgets a disposition changes."""
        self._projects = project_repo
        self._orders = order_repo
        self._lots = lot_repo
        self._files = file_repo
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler
        self._made_item_demands = made_item_demand_repo
        self._made_item_allocations = made_item_allocation_repo
        self._recompute = recompute_schedule
        # Spawns disposition lots inside this transaction.
        self._create_lot = create_lot
        self._settings = settings_repo
        self._work = DispositionRepositories(
            production_orders=order_repo,
            order_items=order_item_repo,
            orders=parent_order_repo,
            interruptions=interruption_repo,
            source_item_demands=source_item_demand_repo,
            source_item_allocations=source_item_allocation_repo,
            reconciler=reconciler,
            bought_allocations=bought_allocation_repo,
        )

    async def execute(
        self,
        actor: User,
        production_order_id: int,
        cmd: RecordProductionOrderCompletionCommand,
    ) -> ProductionOrderResult:
        # Checked before any row lock, so a request that cannot succeed fails
        # early. The order checks run again on the locked order below.
        order = await self._load_order_and_authorize(actor, production_order_id)
        position, inspection_step = await self._load_position_and_check_inspection_permission(
            actor, order
        )

        operator_id, accepted, rejected = self._resolve_completion_split(
            actor, cmd, inspection_step
        )
        disposes = inspection_step is not None and rejected > 0
        work = self._work if disposes else None

        lot, order, position = await lock_lot_and_order(
            self._reconciler,
            self._lots,
            self._orders,
            position,
            production_order_id,
            lot_work=work.order_items if work is not None else None,
            budget_orders=self._projects is not None,
        )
        self._assert_can_record_completion(actor, order, lot)
        # Under the order's lock, which an evidence delete takes as well, so
        # the file checked here is still there at commit.
        await self._assert_evidence_present(order, inspection_step)
        # The order's own cap, accepted plus rejected, first, then what the
        # upstream made available.
        processed_total = sum(c.quantity for c in await self._orders.get_completions(order.id))
        assert_order_completion_within_order_quantity(order, processed_total, cmd.quantity)
        await self._assert_input_available(lot, position, cmd.quantity)
        if disposes:
            assert_disposition_keeps_completed(lot, position, rejected, accepted_now=accepted)

        now = now_utc()
        zone = await tenant_zone(self._settings)
        assert_completion_date_allowed(
            cmd.completion_date,
            now.astimezone(zone).date(),
            order.actual_start.astimezone(zone).date() if order.actual_start else None,
        )
        saved_order = await self._record_completion_and_update_order(
            actor, order, cmd, operator_id, accepted, rejected, processed_total, now
        )
        await self._record_completion_lot_events(
            actor,
            lot,
            position,
            inspection_step,
            cmd,
            accepted,
            rejected,
            operator_id,
            production_order_id,
        )

        outcome = DispositionOutcome()
        if work is not None:
            outcome = await self._handle_disposition(
                actor,
                work,
                lot,
                position,
                cmd.quantity_rework,
                cmd.quantity_scrap,
                rejected,
                accepted,
                now,
            )

        await self._reconciler.run(actor, now)
        # A disposition shrank the lot, after every lifecycle row lock.
        await recompute_time_budgets_of_projects(
            outcome.project_ids,
            self._projects,
            self._lots,
            BudgetOrders(self._orders, self._reconciler.lock_plan),
        )

        await self._publish_events(actor, saved_order, position.id, outcome.events)
        await self._uow.commit()

        await self._recompute_schedule_after_commit(production_order_id)

        log.info(
            f"Recorded completion of {cmd.quantity:.3f} on production order #{production_order_id}."
        )
        return await self._build_result(saved_order.id, outcome.created_lots)

    async def _load_order_and_authorize(
        self, actor: User, production_order_id: int
    ) -> ProductionOrder:
        order = await self._orders.get_by_id(production_order_id)
        if not order:
            raise ProductionOrderNotFoundError(
                f"Production order #{production_order_id} not found."
            )
        self._assert_can_record_completion(actor, order)
        return order

    @staticmethod
    def _assert_can_record_completion(
        actor: User, order: ProductionOrder, lot: ProductionLot | None = None
    ) -> None:
        """The checks before the locks, and again on the locked order and
        its lot, which must not be on hold."""
        ProductionOrderRules.assert_can_update(actor, order)
        held = lot is not None and lot.status == LotStatus.ON_HOLD
        assert_production_order_action(
            LifecycleAction.RECORD_COMPLETION,
            order,
            actor,
            production_order_context(order, lot_held=held),
        )

    async def _load_position_and_check_inspection_permission(
        self, actor: User, order: ProductionOrder
    ) -> tuple[LotPosition, LotStep | None]:
        # The inspection checks need the position before anything is written.
        position = found_or_raise(
            await self._lots.get_position_by_id(order.lot_position_id),
            LotPositionNotFoundError,
            f"Position #{order.lot_position_id} not found.",
        )
        inspection_step = next((s for s in position.steps if s.role == StepRole.INSPECTION), None)
        if inspection_step is not None and not actor.has_permission(Permission.WRITE_INSPECTIONS):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.full_name}) cannot record an inspection completion; "
                "write:inspections is required."
            )
        return position, inspection_step

    def _resolve_completion_split(
        self,
        actor: User,
        cmd: RecordProductionOrderCompletionCommand,
        inspection_step: LotStep | None,
    ) -> tuple[int, float, float]:
        operator_id = resolve_operator_id(actor, cmd.operator_id)
        accepted, rejected = resolve_completion_split(
            cmd.quantity, cmd.quantity_accepted, cmd.quantity_rejected
        )
        assert_whole_completion(
            cmd.quantity, accepted, rejected, cmd.quantity_rework, cmd.quantity_scrap
        )
        assert_valid_disposition(
            inspection_step is not None, rejected, cmd.quantity_rework, cmd.quantity_scrap
        )
        return operator_id, accepted, rejected

    async def _assert_evidence_present(
        self, order: ProductionOrder, inspection_step: LotStep | None
    ) -> None:
        if (  # noqa: SIM102 - completion-evidence guard for production orders; left nested
            inspection_step is not None and inspection_step.inspection_method_requires_evidence
        ):
            if self._files is None or not await self._files.get_by_item_id_and_category(
                order.id, ProductionOrderFileCategory.MEASUREMENT_REPORT
            ):
                raise ProductionOrderMeasurementEvidenceRequiredError(
                    f"Production order #{order.id} uses inspection method "
                    f"{resolve_label(inspection_step.inspection_method_name)!r}, which requires "
                    "evidence; "
                    "upload at least one measurement_report evidence file before recording a "
                    "completion."
                )

    async def _record_completion_and_update_order(
        self,
        actor: User,
        order: ProductionOrder,
        cmd: RecordProductionOrderCompletionCommand,
        operator_id: int,
        accepted: float,
        rejected: float,
        processed_total: float,
        now: datetime,
    ) -> ProductionOrder:
        """Writes the completion row, on top of the `processed_total` execute
        capped the batch against. The order's status, actual_end and
        completed count follow from the rows, through the reconciler."""
        await self._orders.save_completion(
            ProductionOrderCompletion(
                id=0,
                production_order_id=order.id,
                quantity=cmd.quantity,
                quantity_accepted=accepted,
                quantity_rejected=rejected,
                quantity_rework=cmd.quantity_rework,
                quantity_scrap=cmd.quantity_scrap,
                scrap_reason=_scrap_reason(cmd.scrap_reason),
                reject_reason=_scrap_reason(cmd.reject_reason) if rejected > 0 else None,
                completion_date=cmd.completion_date,
                note=cmd.note,
                operator_id=operator_id,
                recorded_by_id=actor.id,
                created=now,
                machine_id=order.machine_id,
            )
        )

        new_processed_total = processed_total + cmd.quantity
        order.changed = now
        order.changes = append_changelog(
            order.changes,
            actor.full_name,
            f"Completion recorded: {accepted:.3f} accepted, {rejected:.3f} rejected "
            f"(processed {new_processed_total:.3f}/{order.quantity:.3f}).",
        )
        return await self._orders.save(order)

    async def _assert_input_available(
        self, lot: ProductionLot, position: LotPosition, processed: float
    ) -> None:
        """Runs under the locks taken in execute, on the locked lot's own
        position object, so two completions on sibling orders cannot both
        pass on the same position total: the pieces the completion
        processes, accepted and rejected together, must fit what reached
        the position and it has not processed yet."""
        if not quantity_gt(processed, 0.0):
            return
        raw_material_arrived = None
        if (
            position.sequence == 1
            and position.kind in (LotPositionKind.INTERNAL, LotPositionKind.MIXED)
            and not lot.is_alteration
        ):
            raw_material_arrived = (
                await self._lots.get_raw_material_arrived_quantity(lot.input_demand_id)
                if lot.input_demand_id is not None
                else 0.0
            )
        assert_completion_within_available(
            position, lot.positions, lot.quantity, processed, raw_material_arrived
        )

    async def _record_completion_lot_events(
        self,
        actor: User,
        lot: ProductionLot,
        position: LotPosition,
        inspection_step: LotStep | None,
        cmd: RecordProductionOrderCompletionCommand,
        accepted: float,
        rejected: float,
        operator_id: int,
        production_order_id: int,
    ) -> None:
        await self._lots.record_event(
            build_lot_event(
                lot.id,
                actor,
                LotEventType.ORDER_COMPLETION_RECORDED,
                "order",
                f"Completion of {cmd.quantity:.3f} recorded on production order "
                f"#{production_order_id} (operator #{operator_id}).",
                entity_id=production_order_id,
                payload={
                    "quantity": cmd.quantity,
                    "quantity_accepted": accepted,
                    "quantity_rejected": rejected,
                    "operator_id": operator_id,
                    "completion_date": cmd.completion_date.isoformat(),
                },
            )
        )
        if inspection_step is not None:
            await self._lots.record_event(
                build_lot_event(
                    lot.id,
                    actor,
                    LotEventType.INSPECTION_RECORDED,
                    "order",
                    f"Inspection ({resolve_label(inspection_step.inspection_method_name)}) "
                    "recorded on "
                    f"production order #{production_order_id}: {accepted:.3f} "
                    f"accepted, {rejected:.3f} rejected.",
                    entity_id=production_order_id,
                    payload={
                        "quantity_accepted": accepted,
                        "quantity_rejected": rejected,
                        "inspection_method_id": inspection_step.inspection_method_id,
                        "inspection_method_name": resolve_label(
                            inspection_step.inspection_method_name
                        ),
                        "reject_reason": cmd.reject_reason if rejected > 0 else None,
                    },
                )
            )

    async def _publish_events(
        self,
        actor: User,
        saved_order: ProductionOrder,
        position_id: int,
        lot_events: list[DomainEvent],
    ) -> None:
        """Staged before the commit and the fallible recompute; lost events,
        unlike a stale schedule, cannot be recovered by running it again.
        ProductionOrderCompleted and the lot's status events come from the
        reconciler, and the position's completed count is read as it
        stored it."""
        position = found_or_raise(
            await self._lots.get_position_by_id(position_id),
            LotPositionNotFoundError,
            f"Position #{position_id} not found.",
        )
        await self._bus.publish(
            ProductionOrderCompletionRecorded(
                production_order_id=saved_order.id,
                lot_position_id=position.id,
                quantity_completed=position.quantity_completed,
                actor_id=actor.id,
            )
        )
        for event in lot_events:
            await self._bus.publish(event)

    async def _recompute_schedule_after_commit(self, production_order_id: int) -> None:
        await recompute_schedule_after_commit(
            self._recompute,
            after=(
                f"recording completion on "
                f"production order #{production_order_id}; the completion itself "
                f"is committed and its events are published."
            ),
        )

    async def _build_result(
        self, saved_order_id: int, created_lots: list[CreatedLotResult]
    ) -> ProductionOrderResult:
        result_order = await self._orders.get_by_id(saved_order_id)
        if not result_order:
            raise ProductionOrderNotFoundError(
                f"Production order #{saved_order_id} not found after save."
            )
        result = ProductionOrderMapper.to_result(result_order)
        result.created_lots = created_lots
        return result

    async def _handle_disposition(
        self,
        actor: User,
        work: DispositionRepositories,
        lot: ProductionLot,
        inspection_position: LotPosition,
        quantity_rework: float,
        quantity_scrap: float,
        rejected: float,
        accepted: float,
        now: datetime,
    ) -> DispositionOutcome:
        """Applies the shared disposition for rejected pieces of an
        inspection, without committing."""
        closing_event = build_lot_event(
            lot.id,
            actor,
            LotEventType.LOT_CLOSED_SHORT,
            "lot",
            f"Lot closed short by {rejected:.3f} rejected piece(s); quantity now "
            f"{lot.quantity - rejected:.3f}.",
            payload={"rejected": rejected, "new_quantity": lot.quantity - rejected},
        )
        return await apply_disposition(
            lots_repo=self._lots,
            work=work,
            made_item_demand_repo=self._made_item_demands,
            made_item_allocation_repo=self._made_item_allocations,
            create_lot=self._create_lot,
            actor=actor,
            lot=lot,
            position=inspection_position,
            removed_quantity=rejected,
            quantity_rework=quantity_rework,
            quantity_scrap=quantity_scrap,
            create_replacement=True,
            closing_event=closing_event,
            replacement_note=f"Replacement for {rejected:.3f} rejected piece(s) from lot "
            f"{lot.lot_number} (QA reject, scrapped).",
            accepted_now=accepted,
            now=now,
        )


def _scrap_reason(reason: str | None) -> ScrapReason | None:
    return ScrapReason(reason) if reason is not None else None
