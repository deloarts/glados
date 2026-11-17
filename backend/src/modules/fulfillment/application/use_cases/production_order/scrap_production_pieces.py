"""
Scraps pieces of an internal production order's own position while it is
IN_PROGRESS: records a ProductionOrderCompletion with the scrapped
quantity entirely rejected (nothing accepted), then runs the same
disposition core the QA/inspection reject path uses
(piece_disposition.apply_disposition) against that position directly, no
inspection step required. Unlike the QA path there is no rework option:
scrapped pieces are gone, not sent back for alteration. The operator
can opt out of the replacement lot the disposition would otherwise spawn,
in which case the origin lot's demand coverage is simply reduced instead.

Mirrors record_production_order_completion.py's shape for the parts this
shares with it (order/permission loading, the lot, then the order and the
lot's other work locked before the capacity and the processed total are
read, the completion row, the order-level processed-total cap, the
disposition recording its facts before the lifecycle reconciler derives
every status from them, the made demands of the lot included);
ScrapLotPieces (scrap_lot_pieces.py) is a thin resolver in front of this use
case for the lot-detail entry point, where the order isn't already known.
"""

from datetime import datetime

from src.modules.fulfillment.application.dto.production_lot_dto import ScrapPiecesResult
from src.modules.fulfillment.application.dto.production_order_dto import (
    ScrapProductionPiecesCommand,
)
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotMapper
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
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.errors import LotPositionNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.domain.events.lot_events import PiecesScrapped
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.lot_rules import assert_disposition_keeps_completed
from src.modules.fulfillment.domain.services.lot_rules import assert_scrap_allowed
from src.modules.fulfillment.domain.services.production_order_rules import ProductionOrderRules
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_order_completion_within_order_quantity,
)
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_production_order_action,
)
from src.modules.fulfillment.domain.services.production_order_rules import production_order_context
from src.modules.fulfillment.domain.services.production_order_rules import resolve_operator_id
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
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
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


class ScrapProductionPieces:
    def __init__(
        self,
        order_repo: IProductionOrderRepository,
        lot_repo: IProductionLotRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        order_item_repo: IOrderItemRepository,
        parent_order_repo: IOrderRepository,
        interruption_repo: IProductionOrderInterruptionRepository,
        source_item_demand_repo: ISourceItemDemandRepository,
        source_item_allocation_repo: ISourceItemAllocationRepository,
        made_item_demand_repo: IMadeItemDemandItemRepository,
        made_item_allocation_repo: IMadeItemAllocationRepository,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        create_lot: CreateLot,
        settings_repo: IFulfillmentSettingsRepository,
        bought_allocation_repo: IBoughtItemAllocationRepository,
        project_repo: IProjectQueries | None = None,
    ) -> None:
        """The bought allocations settle the raw material demand of a lot
        the scrap empties. The settings give the tenant's timezone, whose
        date the scrap is booked on."""
        self._projects = project_repo
        self._orders = order_repo
        self._lots = lot_repo
        self._bus = event_bus
        self._uow = uow
        self._reconciler = reconciler
        self._made_item_demands = made_item_demand_repo
        self._made_item_allocations = made_item_allocation_repo
        self._recompute = recompute_schedule
        self._create_lot = create_lot
        self._settings = settings_repo
        # What the disposition writes besides the lot and its allocations.
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

    async def execute(self, actor: User, cmd: ScrapProductionPiecesCommand) -> ScrapPiecesResult:
        # Checked before any row lock, so a request that cannot succeed fails
        # early. The order checks run again on the locked order below.
        order = await self._load_order_and_authorize(actor, cmd.production_order_id)

        position = found_or_raise(
            await self._lots.get_position_by_id(order.lot_position_id),
            LotPositionNotFoundError,
            f"Position #{order.lot_position_id} not found.",
        )

        now = now_utc()
        operator_id = resolve_operator_id(actor, cmd.operator_id)

        # Locked in the shared order, lot first and then the order with the
        # lot's other work, which the disposition may cut, like
        # RecordProductionOrderCompletion: concurrent scraps and completions
        # on one lot serialize, and the capacity, the processed total and
        # every write below use the locked rows.
        lot, order, position = await lock_lot_and_order(
            self._reconciler,
            self._lots,
            self._orders,
            position,
            order.id,
            lot_work=self._work.order_items,
            budget_orders=self._projects is not None,
        )
        self._assert_can_scrap(actor, order, lot)
        assert_edit_version(order, cmd.expected_edit_version, what=f"Production order #{order.id}")
        assert_edit_version(lot, cmd.expected_lot_edit_version, what=f"Lot #{lot.id}")

        raw_material_arrived = await self._resolve_raw_material_arrived(lot, position)
        assert_scrap_allowed(lot, position, cmd.quantity, actor, raw_material_arrived)
        assert_disposition_keeps_completed(lot, position, cmd.quantity)

        # A scrap cannot be taken back, so both rows it books on move.
        bump_edit_version(order)
        bump_edit_version(lot)
        completion_id = await self._record_completion_and_update_order(
            actor, order, cmd, operator_id, now
        )

        closing_event = build_lot_event(
            lot.id,
            actor,
            LotEventType.PIECES_SCRAPPED,
            "lot",
            f"{cmd.quantity:.3f} piece(s) scrapped at position #{position.id} "
            f"({cmd.reason}); quantity now {lot.quantity - cmd.quantity:.3f}.",
            entity_id=order.id,
            payload={
                "production_order_id": order.id,
                "position_id": position.id,
                "quantity": cmd.quantity,
                "reason": cmd.reason,
            },
        )
        outcome = await apply_disposition(
            lots_repo=self._lots,
            work=self._work,
            made_item_demand_repo=self._made_item_demands,
            made_item_allocation_repo=self._made_item_allocations,
            create_lot=self._create_lot,
            actor=actor,
            lot=lot,
            position=position,
            removed_quantity=cmd.quantity,
            quantity_rework=0.0,
            quantity_scrap=cmd.quantity,
            create_replacement=cmd.create_replacement,
            closing_event=closing_event,
            replacement_note=f"Replacement for {cmd.quantity:.3f} scrapped piece(s) from lot "
            f"{lot.lot_number}.",
            replacement_required_delivery_date=lot.required_delivery_date,
            replacement_priority=lot.priority,
            now=now,
        )
        await self._reconciler.run(actor, now)
        # The lot shrank, after every lifecycle row lock.
        await recompute_time_budgets_of_projects(
            outcome.project_ids,
            self._projects,
            self._lots,
            BudgetOrders(self._orders, self._reconciler.lock_plan),
        )

        replacement = next(
            (c for c in outcome.created_lots if c.disposition == "replacement"), None
        )
        scrapped_event = PiecesScrapped(
            lot_id=lot.id,
            lot_number=lot.lot_number,
            position_id=position.id,
            production_order_id=order.id,
            quantity=cmd.quantity,
            reason=cmd.reason,
            replacement_lot_id=replacement.id if replacement else None,
            replacement_lot_number=replacement.lot_number if replacement else None,
            actor_id=actor.id,
            completion_id=completion_id,
        )

        # Staged before the commit and the fallible recompute;
        # ProductionOrderCompleted comes from the reconciler.
        for event in [*outcome.events, scrapped_event]:
            await self._bus.publish(event)
        await self._uow.commit()
        await self._recompute_schedule_after_commit(order.id)

        log.info(
            f"Scrapped {cmd.quantity:.3f} piece(s) on production order #{order.id} ({cmd.reason})."
        )
        return await self._build_result(lot.id, outcome)

    async def _load_order_and_authorize(
        self, actor: User, production_order_id: int
    ) -> ProductionOrder:
        order = await self._orders.get_by_id(production_order_id)
        if not order:
            raise ProductionOrderNotFoundError(
                f"Production order #{production_order_id} not found."
            )
        self._assert_can_scrap(actor, order)
        return order

    @staticmethod
    def _assert_can_scrap(
        actor: User, order: ProductionOrder, lot: ProductionLot | None = None
    ) -> None:
        """The checks before the locks, and again on the locked order and
        its lot, which must not be on hold."""
        ProductionOrderRules.assert_can_update(actor, order)
        held = lot is not None and lot.status == LotStatus.ON_HOLD
        assert_production_order_action(
            LifecycleAction.SCRAP, order, actor, production_order_context(order, lot_held=held)
        )

    async def _resolve_raw_material_arrived(
        self, lot: ProductionLot, position: LotPosition
    ) -> float | None:
        """Mirrors RecordProductionOrderCompletion's own resolution: only
        matters for a lot's very first position, INTERNAL/MIXED, sourced
        from raw material rather than a rework/alteration; every other
        position's capacity is unconstrained by this (available_input
        treats None as "unconstrained", the correct default for an
        alteration lot or a later position, whose availability comes from
        its predecessor instead)."""
        if (
            position.sequence == 1
            and position.kind in (LotPositionKind.INTERNAL, LotPositionKind.MIXED)
            and not lot.is_alteration
        ):
            return (
                await self._lots.get_raw_material_arrived_quantity(lot.input_demand_id)
                if lot.input_demand_id is not None
                else 0.0
            )
        return None

    async def _record_completion_and_update_order(
        self,
        actor: User,
        order: ProductionOrder,
        cmd: ScrapProductionPiecesCommand,
        operator_id: int,
        now: datetime,
    ) -> int:
        """Writes the scrap's completion row and returns its id. The order's
        status and actual_end follow from the rows, through the reconciler."""
        processed_total = sum(c.quantity for c in await self._orders.get_completions(order.id))
        assert_order_completion_within_order_quantity(order, processed_total, cmd.quantity)

        saved_completion = await self._orders.save_completion(
            ProductionOrderCompletion(
                id=0,
                production_order_id=order.id,
                quantity=cmd.quantity,
                quantity_accepted=0.0,
                quantity_rejected=cmd.quantity,
                quantity_scrap=cmd.quantity,
                scrap_reason=ScrapReason(cmd.reason),
                completion_date=now.astimezone(await tenant_zone(self._settings)).date(),
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
            f"{cmd.quantity:.3f} piece(s) scrapped ({cmd.reason}; processed "
            f"{new_processed_total:.3f}/{order.quantity:.3f}).",
        )
        await self._orders.save(order)
        return saved_completion.id

    async def _recompute_schedule_after_commit(self, production_order_id: int) -> None:
        await recompute_schedule_after_commit(
            self._recompute,
            after=(
                f"scrapping pieces on production order "
                f"#{production_order_id}; the scrap itself is committed and its events "
                f"are published."
            ),
        )

    async def _build_result(self, lot_id: int, outcome: DispositionOutcome) -> ScrapPiecesResult:
        fresh_lot = await self._lots.get_by_id(lot_id)
        assert fresh_lot is not None
        return ScrapPiecesResult(
            lot=LotMapper.to_summary(fresh_lot), created_lots=outcome.created_lots
        )
