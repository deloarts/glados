"""Creates a ProductionLot from a made item's routing: every process becomes
a LotStep, grouped into positions like the made item's own process groups.
After creation the lot's grouping is independent of the made item. Demand
allocations can be linked, only to demands of the lot's project and of the
made item the lot builds, and a routing without processes is legal. A lot a
user creates needs an active project and a made item new work may name.

The lot, its positions and the production orders auto-queued for its
inspection positions are registered with the lifecycle reconciler as rows
this transaction created, and the reconciler derives their statuses: an
inspection position with its queued order is INTERNAL and the lot past
DRAFT. The made demands a lot is linked to are locked and registered with
the reconciler too, which derives them from the lot's derived status;
create_no_commit leaves the run to its caller.
"""

from collections.abc import Iterable
from datetime import datetime

from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.domain.errors import InspectionMethodConfigurationError
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.policies.inspection_method_rules import seed_inspection_estimates
from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.catalogue.ports.outbound.catalogue_queries import IInspectionMethodQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IMadeItemQueries
from src.modules.fulfillment.application.dto.production_lot_dto import CreateLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import LotDemandAllocationInput
from src.modules.fulfillment.application.dto.production_lot_dto import LotResult
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotMapper
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.production_order_factory import (
    build_queued_production_order,
)
from src.modules.fulfillment.application.services.queue_scope_locks import lock_queue_scopes_first
from src.modules.fulfillment.application.services.source_item_demand_factory import (
    build_source_item_demand,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import DemandItemNotFoundError
from src.modules.fulfillment.domain.errors import LotAlterationSourceConflictError
from src.modules.fulfillment.domain.events.lot_events import LotCreated
from src.modules.fulfillment.domain.services.lot_event_service import build_lot_event
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.services.made_item_demand_rules import MadeItemAllocationRules
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_origin_disposition import LotOriginDisposition
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.retry_on_conflict import commit_with_number_retry
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.policies.project_activity import assert_project_active
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class CreateLot:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        made_item_repo: IMadeItemQueries,
        demand_repo: IMadeItemDemandItemRepository,
        allocation_repo: IMadeItemAllocationRepository,
        settings_repo: IFulfillmentSettingsRepository,
        source_item_demand_repo: ISourceItemDemandRepository,
        order_repo: IProductionOrderRepository,
        inspection_method_repo: IInspectionMethodQueries,
        machine_repo: IProductionMachineRepository,
        *,
        uow: IUnitOfWork,
        event_bus: IEventBus,
        reconciler: LifecycleReconciler,
        # None only for unit tests that predate the project check; the deps
        # factory always passes it.
        project_repo: IProjectQueries | None = None,
        recompute_schedule: ScheduleRecompute | None = None,
    ) -> None:
        """`reconciler` is the request's lifecycle reconciler; a caller of
        create_no_commit runs the same one, and requests the schedule walk
        its own commit needs."""
        self._lots = lot_repo
        self._made_items = made_item_repo
        self._demands = demand_repo
        self._allocations = allocation_repo
        self._settings = settings_repo
        self._source_item_demands = source_item_demand_repo
        self._orders = order_repo
        self._inspection_methods = inspection_method_repo
        self._machines = machine_repo
        self._uow = uow
        self._bus = event_bus
        self._reconciler = reconciler
        self._projects = project_repo
        self._recompute = recompute_schedule

    async def execute(self, actor: User, cmd: CreateLotCommand) -> LotResult:
        # Concurrent creations can collide on the lot number; the unit of
        # work is rebuilt from scratch, so it is safe to re-run after a
        # rollback (see retry_on_conflict.py).
        async def _create_and_stage_event() -> ProductionLot:
            """The lot write, its reconciled statuses and its outbox event in
            one transaction, so a retry can neither lose the event nor
            publish it twice."""
            lot = await self.create_no_commit(actor, cmd)
            await self._reconciler.run(actor, now_utc())
            await self._bus.publish(
                LotCreated(
                    lot_id=lot.id,
                    made_item_id=lot.made_item_id,
                    creator_id=lot.creator_id,
                )
            )
            return lot

        saved_lot = await commit_with_number_retry(
            self._uow, _create_and_stage_event, reconciler=self._reconciler
        )
        # The orders auto-queued for its inspection positions join their queues.
        await recompute_schedule_after_commit(
            self._recompute, after=f"creating lot {saved_lot.lot_number!r}; the lot is committed."
        )
        log.info(f"Created lot {saved_lot.lot_number!r} for made item #{cmd.made_item_id}.")
        result_lot = await self._lots.get_by_id(saved_lot.id)
        assert result_lot is not None
        return LotMapper.to_result(result_lot)

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
    ) -> ProductionLot:
        """The creation core without a commit, so callers such as the
        inspection disposition can fold a spawned lot into their own
        transaction. The caller runs the reconciler, which derives the made
        demands of `cmd.demand_allocations` too (module docstring).

        A rework lot forces its source to the originating lot's made item;
        the origin fields stamp the lineage. The disposition flow passes
        check_create_permission=False, because the lot is a side effect of a
        completion the caller already authorized, and inspectors should not
        need lot-creation rights to record a reject. Such a lot continues
        work that already exists, so it also skips the checks a new lot
        needs: an active project and a made item new work may name.
        """
        if check_create_permission:
            LotRules.assert_can_create(actor)

        made_item = found_or_raise(
            await self._made_items.get_by_id(cmd.made_item_id),
            MadeItemNotFoundError,
            f"Catalogue item #{cmd.made_item_id} not found.",
        )
        if check_create_permission:
            MadeItemCatalogueRules.assert_item_demandable(made_item)
            await self._assert_project_active(cmd.project_id)
            LotRules.assert_whole_lot_quantities(
                cmd.quantity, [a.quantity for a in cmd.demand_allocations]
            )

        LotRules.assert_allocations_within_quantity(
            cmd.quantity, sum(a.quantity for a in cmd.demand_allocations)
        )
        # Every writer locks in one order: queue scopes (queue_scope_locks.py),
        # then lifecycle rows, then the number's counter (number_counters.py).
        # The demands are locked before they are read, so two lots linking
        # the same demand cannot both pass the overallocation check and the
        # demand cannot become fulfilled or canceled before the commit. A
        # sweep over several lots locks them all before its first lot.
        await self.lock_routing_queue_scopes([cmd.made_item_id])
        if cmd.demand_allocations:
            self._reconciler.touch_demands(
                LifecycleAggregate.MADE_DEMANDS,
                [a.demand_item_id for a in cmd.demand_allocations],
            )
            await self._reconciler.lock_touched()
        alteration_source_id = forced_source_made_item_id or await self._resolve_alteration_source(
            cmd.demand_allocations
        )

        now = now_utc()
        priority = cmd.priority or await self._prefill_priority(cmd)
        lot_number = await self._lots.next_lot_number(
            (await self._settings.get_made_items()).lot_number_format
        )

        effective_source_item_id = None if alteration_source_id else made_item.source_item_id
        # Only a source-item source is gated, and only while the toggle is on.
        source_approval_status = (
            SourceApprovalStatus.PENDING
            if (
                (await self._settings.get_production()).require_source_item_approval
                and effective_source_item_id is not None
            )
            else SourceApprovalStatus.NOT_REQUIRED
        )

        lot = ProductionLot(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Lot created."),
            lot_number=lot_number,
            quantity=cmd.quantity,
            status=LotStatus.default(),
            priority=priority,
            note=cmd.note,
            required_delivery_date=cmd.required_delivery_date,
            creator_id=actor.id,
            made_item_id=cmd.made_item_id,
            project_id=cmd.project_id,
            input_demand_id=None,
            source_bought_item_id=None if alteration_source_id else made_item.bought_item_id,
            source_item_id=effective_source_item_id,
            source_made_item_id=alteration_source_id,
            origin_lot_id=origin_lot_id,
            origin_disposition=origin_disposition,
            source_approval_status=source_approval_status,
        )
        saved_lot = await self._lots.save(lot)
        self._reconciler.touch_lots([saved_lot.id], created=True)
        await self._lots.record_event(
            build_lot_event(
                saved_lot.id,
                actor,
                LotEventType.LOT_CREATED,
                "lot",
                f"Lot {saved_lot.lot_number} created for made item #{cmd.made_item_id} "
                f"(qty {cmd.quantity}).",
                payload={"made_item_id": cmd.made_item_id, "quantity": cmd.quantity},
            )
        )

        # While pending, approval creates the demand later.
        has_material_source = (
            saved_lot.source_bought_item_id is not None or saved_lot.source_item_id is not None
        )
        if (
            create_source_item_demand
            and has_material_source
            and saved_lot.source_approval_status != SourceApprovalStatus.PENDING
        ):
            await self._create_source_item_demand(actor, saved_lot, now)

        await self._snapshot_routing(actor, saved_lot, made_item, now)

        for allocation_input in sorted(cmd.demand_allocations, key=lambda a: a.demand_item_id):
            await self._link_demand_allocation(actor, saved_lot, allocation_input)

        return saved_lot

    async def _assert_project_active(self, project_id: int) -> None:
        if self._projects is None:
            return
        # Locked in shared mode before it is checked, so a concurrent delete
        # of the project waits for this creation and then counts it
        # (IProjectQueries.lock_for_share).
        await self._projects.lock_for_share([project_id])
        project = found_or_raise(
            await self._projects.get_by_id(project_id),
            ProjectNotFoundError,
            f"Project #{project_id} not found.",
        )
        assert_project_active(project)

    async def _create_source_item_demand(
        self, actor: User, lot: ProductionLot, now: datetime
    ) -> None:
        """Creates the material demand of a lot with a bought or source item
        source right away."""
        demand = build_source_item_demand(
            lot,
            actor,
            quantity=lot.quantity,
            unit="pcs",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=None,
            desired_delivery_date=None,
        )
        saved_demand = await self._source_item_demands.save(demand)
        lot.input_demand_id = saved_demand.id
        lot.changed = now
        lot.changes = append_changelog(
            lot.changes, actor.full_name, f"Linked source item demand #{saved_demand.id}."
        )
        await self._lots.save(lot)

    async def _prefill_priority(self, cmd: CreateLotCommand) -> UrgencyClass:
        if not cmd.demand_allocations:
            return UrgencyClass.default()
        demand_ids = [a.demand_item_id for a in cmd.demand_allocations]
        demands = await self._demands.get_by_ids(demand_ids)
        if any(d.high_priority for d in demands):
            return UrgencyClass.HIGH
        return UrgencyClass.default()

    async def _resolve_alteration_source(
        self, demand_allocations: list[LotDemandAllocationInput]
    ) -> int | None:
        """If any linked demand is an alteration, all must be, and all must
        name the same made item, since a lot has one rework source."""
        if not demand_allocations:
            return None
        demand_ids = [a.demand_item_id for a in demand_allocations]
        demands = await self._demands.get_by_ids(demand_ids)
        alteration_demands = [d for d in demands if d.is_alteration]
        if not alteration_demands:
            return None
        if len(alteration_demands) != len(demands):
            raise LotAlterationSourceConflictError(
                "Cannot mix alteration and non-alteration demand in a single lot."
            )
        sources = {d.alteration_of_made_item_id for d in alteration_demands}
        if len(sources) > 1:
            raise LotAlterationSourceConflictError(
                "All alteration demands linked to a lot must rework the same made item."
            )
        return sources.pop()

    async def _snapshot_routing(
        self, actor: User, lot: ProductionLot, made_item: MadeItem, now: datetime
    ) -> None:
        processes = sorted(made_item.processes, key=lambda p: p.position)

        # Runs of equal group_index become one position; inspection
        # processes are always alone in their group.
        groups: list[list[MadeItemProcess]] = []
        for process in processes:
            if groups and groups[-1][0].group_index == process.group_index:
                groups[-1].append(process)
            else:
                groups.append([process])

        position_sequence = 0
        step_sequence = 0
        # Inspection positions with their method id, auto-queued in one pass
        # once every position exists.
        inspection_positions: list[tuple[LotPosition, int | None]] = []
        for group in groups:
            position_sequence += 1
            step_sequence, saved_position = await self._save_snapshot_position(
                actor, lot, now, position_sequence, step_sequence, group
            )
            if group[0].role == StepRole.INSPECTION:
                inspection_positions.append((saved_position, group[0].inspection_method_id))

        last_process_is_inspection = bool(processes) and processes[-1].role == StepRole.INSPECTION
        production_settings = await self._settings.get_production()
        if production_settings.require_qa and not last_process_is_inspection:
            default_method_id = production_settings.default_inspection_method_id
            method = (
                await self._inspection_methods.get_by_id(default_method_id)
                if default_method_id is not None
                else None
            )
            if method is None or method.archived:
                raise InspectionMethodConfigurationError(
                    "require_qa is on but AdminProductionSettings."
                    "default_inspection_method_id is not set to an existing, non-archived "
                    "inspection method."
                )
            position_sequence += 1
            qa_position = await self._save_snapshot_qa_position(
                actor, lot, now, position_sequence, step_sequence + 1, method
            )
            method_cache: dict[int, InspectionMethod | None] = {method.id: method}
            inspection_positions.append((qa_position, method.id))
        else:
            method_cache = {}

        # Resolve every pre-fill machine first, then lock all queue scopes
        # in sorted order before queuing, as concurrent writers may share them.
        resolved_positions: list[tuple[LotPosition, int | None]] = [
            (position, await self._resolve_default_machine_id(method_id, method_cache))
            for position, method_id in inspection_positions
        ]
        for scope in sorted(
            {(machine_id, None) for _, machine_id in resolved_positions},
            key=lambda s: (s[0] is None, s[0] or 0, s[1] is None, s[1] or 0),
        ):
            await self._orders.lock_queue_scope(scope[0], scope[1])

        for position, machine_id in resolved_positions:
            await self._auto_queue_inspection_position(actor, lot, now, position, machine_id)

    async def lock_routing_queue_scopes(self, made_item_ids: Iterable[int]) -> None:
        """Locks the queues the inspection positions of new lots of these
        made items will be queued in, before any row lock
        (queue_scope_locks.py). create_no_commit calls it for its own lot, a
        sweep that locks its demands before its first lot calls it for all
        of them first, and _snapshot_routing takes the same locks again;
        locks the transaction already holds are granted at once."""
        settings = await self._settings.get_production()
        method_cache: dict[int, InspectionMethod | None] = {}
        machine_ids: set[int | None] = set()
        for made_item_id in sorted(set(made_item_ids)):
            made_item = await self._made_items.get_by_id(made_item_id)
            if made_item is None:
                continue
            processes = sorted(made_item.processes, key=lambda p: p.position)
            method_ids = [
                p.inspection_method_id for p in processes if p.role == StepRole.INSPECTION
            ]
            last_is_inspection = bool(processes) and processes[-1].role == StepRole.INSPECTION
            if settings.require_qa and not last_is_inspection:
                method_ids.append(settings.default_inspection_method_id)
            for method_id in method_ids:
                machine_ids.add(await self._resolve_default_machine_id(method_id, method_cache))
        await lock_queue_scopes_first(self._orders, [(m, None) for m in machine_ids])

    async def _resolve_default_machine_id(
        self, method_id: int | None, method_cache: dict[int, InspectionMethod | None]
    ) -> int | None:
        """The inspection method's default QA machine, or None if it is
        missing, archived or no longer a QA machine. Never raises; the default
        is validated when the method is saved."""
        if method_id is None:
            return None
        if method_id not in method_cache:
            method_cache[method_id] = await self._inspection_methods.get_by_id(method_id)
        method = method_cache[method_id]
        if method is None or method.default_machine_id is None:
            return None
        machine = await self._machines.get_by_id(method.default_machine_id)
        if machine is None or not machine.is_qa_machine:
            return None
        return machine.id

    async def _save_snapshot_position(
        self,
        actor: User,
        lot: ProductionLot,
        now: datetime,
        position_sequence: int,
        step_sequence: int,
        group: list[MadeItemProcess],
    ) -> tuple[int, LotPosition]:
        position = LotPosition(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Position created (lot snapshot)."),
            sequence=position_sequence,
            kind=LotPositionKind.default(),
            status=LotPositionStatus.default(),
            quantity=lot.quantity,
            quantity_completed=0.0,
            note=None,
            creator_id=actor.id,
            lot_id=lot.id,
        )
        saved_position = await self._lots.save_position(position)
        self._reconciler.touch_positions([saved_position.id], created=True)

        steps = []
        for process in group:
            step_sequence += 1
            step = LotStep(
                id=0,
                created=now,
                note=process.note,
                estimated_setup_minutes=process.estimated_setup_minutes,
                estimated_minutes_per_piece=process.estimated_minutes_per_piece,
                sequence=step_sequence,
                creator_id=actor.id,
                fabrication_method_id=process.fabrication_method_id,
                lot_id=lot.id,
                position_id=saved_position.id,
                source_process_id=process.id,
                role=process.role,
                inspection_method_id=process.inspection_method_id,
            )
            steps.append(await self._lots.save_step(step))
        # The auto-queued order's duration is sized from these steps.
        saved_position.steps = steps
        return step_sequence, saved_position

    async def _save_snapshot_qa_position(
        self,
        actor: User,
        lot: ProductionLot,
        now: datetime,
        position_sequence: int,
        step_sequence: int,
        method: InspectionMethod,
    ) -> LotPosition:
        """Appends the trailing QA position required by require_qa, with
        estimates seeded from the default inspection method."""
        position = LotPosition(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog(
                [], actor.full_name, "Position created (auto QA, require_qa)."
            ),
            sequence=position_sequence,
            kind=LotPositionKind.default(),
            status=LotPositionStatus.default(),
            quantity=lot.quantity,
            quantity_completed=0.0,
            note=None,
            creator_id=actor.id,
            lot_id=lot.id,
        )
        saved_position = await self._lots.save_position(position)
        self._reconciler.touch_positions([saved_position.id], created=True)
        setup_minutes, minutes_per_piece = seed_inspection_estimates(method, None, None)
        step = LotStep(
            id=0,
            created=now,
            note=None,
            estimated_setup_minutes=setup_minutes,
            estimated_minutes_per_piece=minutes_per_piece,
            sequence=step_sequence,
            creator_id=actor.id,
            fabrication_method_id=None,
            lot_id=lot.id,
            position_id=saved_position.id,
            source_process_id=None,
            role=StepRole.INSPECTION,
            inspection_method_id=method.id,
        )
        saved_step = await self._lots.save_step(step)
        saved_position.steps = [saved_step]
        return saved_position

    async def _auto_queue_inspection_position(
        self,
        actor: User,
        lot: ProductionLot,
        now: datetime,
        position: LotPosition,
        machine_id: int | None,
    ) -> None:
        """Inspection positions are born with a queued order, which makes them
        INTERNAL, because an inspection is real trackable work, not a step
        awaiting routing. The order runs through the manual scheduling path.
        The caller has already locked the queue scope."""
        template = (await self._settings.get_production()).production_order_number_format
        note = (
            f"Auto-queued QA inspection (born internal, machine #{machine_id})."
            if machine_id is not None
            else "Auto-queued QA inspection (born internal)."
        )
        order = await build_queued_production_order(
            actor,
            position,
            position.quantity,
            lot.priority,
            machine_id=machine_id,
            machine_pool_id=None,
            order_repo=self._orders,
            number_template=template,
            now=now,
            changelog_note=note,
        )
        self._reconciler.touch_production_orders([order.id], created=True)
        position.production_orders = [order]
        position.changed = now
        position.changes = append_changelog(position.changes, actor.full_name, note)
        await self._lots.save_position(position)
        await self._lots.record_event(
            build_lot_event(
                lot.id,
                actor,
                LotEventType.POSITION_ASSIGNED_INTERNAL,
                "position",
                f"Position #{position.id} auto-queued for QA inspection (born internal).",
                entity_id=position.id,
                payload={"production_order_ids": [order.id]},
            )
        )

    async def _link_demand_allocation(
        self, actor: User, lot: ProductionLot, allocation_input: LotDemandAllocationInput
    ) -> None:
        # Read under the lock create_no_commit took.
        demand = found_or_raise(
            await self._demands.get_by_id(allocation_input.demand_item_id),
            DemandItemNotFoundError,
            f"Demand #{allocation_input.demand_item_id} not found.",
        )

        MadeItemAllocationRules.assert_not_terminal(demand)
        LotRules.assert_demand_project_matches(lot.project_id, demand.project_id, demand.id)
        LotRules.assert_demand_made_item_matches(lot.made_item_id, demand.made_item_id, demand.id)

        existing_allocations = await self._allocations.get_by_demand_item_id(demand.id)
        existing_total = sum(a.quantity for a in existing_allocations)
        MadeItemAllocationRules.assert_no_overallocation(
            demand, existing_total, allocation_input.quantity
        )

        await self._allocations.save(
            MadeItemDemandAllocation(
                demand_item_id=demand.id,
                lot_id=lot.id,
                quantity=allocation_input.quantity,
                source=MadeItemAllocationSource.LOT,
            )
        )
