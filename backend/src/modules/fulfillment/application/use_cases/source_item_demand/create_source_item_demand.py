"""
Triggered by the "Demand Source Item" action on a lot row. One-shot per lot:
a lot can only ever link one source item demand, tracked via
ProductionLot.input_demand_id.
Reads the lot's own material source directly (seeded from the made item at
creation, switchable per lot via SwitchLotMaterialSource) rather than
walking through the made item, a lot whose source is a rework MadeItem
can't be demanded through this flow (stock-consumption is deferred).

Also guards against source_approval_status being pending/rejected: no
settings lookup is needed here, the stored column is authoritative once
the require_source_item_approval toggle backfill has run (see
UpdateProductionSettings), so a plain field check on the already-loaded
lot is enough. The lot's project must be active. The new demand is
registered with the lifecycle reconciler, which keeps its derived status.
"""

from src.modules.fulfillment.application.dto.source_item_demand_dto import (
    CreateSourceItemDemandCommand,
)
from src.modules.fulfillment.application.dto.source_item_demand_dto import SourceItemDemandResult
from src.modules.fulfillment.application.mappers.source_item_demand_mapper import (
    SourceItemDemandMapper,
)
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.source_item_demand_factory import (
    build_source_item_demand,
)
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.errors import LotHasNoMaterialSourceError
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.domain.errors import LotRawMaterialAlreadyLinkedError
from src.modules.fulfillment.domain.errors import SourceItemApprovalRequiredError
from src.modules.fulfillment.domain.errors import SourceItemRequiresReworkStockError
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.quantities import assert_whole_pieces
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.policies.project_activity import assert_project_active
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class CreateSourceItemDemand:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        demand_repo: ISourceItemDemandRepository,
        project_repo: IProjectQueries,
        recompute_schedule: RecomputeMachineSchedule | None = None,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._lots = lot_repo
        self._demands = demand_repo
        self._projects = project_repo
        self._recompute = recompute_schedule
        self._uow = uow
        self._reconciler = reconciler

    async def execute(
        self, actor: User, cmd: CreateSourceItemDemandCommand
    ) -> SourceItemDemandResult:
        lot = found_or_raise(
            await self._lots.get_by_id(cmd.lot_id),
            LotNotFoundError,
            f"Lot #{cmd.lot_id} not found.",
        )
        # The project is locked in shared mode before the lot, as every
        # creation of work locks its project (IProjectQueries), and the
        # lot is locked through the request's lock plan and read again, so
        # its link checked below cannot change before the commit.
        await self._projects.lock_for_share([lot.project_id])
        await self._reconciler.lock_touched(
            also=AggregateIds.of({LifecycleAggregate.LOTS: [cmd.lot_id]})
        )
        lot = found_or_raise(
            await self._lots.get_by_id(cmd.lot_id),
            LotNotFoundError,
            f"Lot #{cmd.lot_id} not found.",
        )
        LotRules.assert_can_update(actor, lot)

        if lot.input_demand_id is not None:
            raise LotRawMaterialAlreadyLinkedError(
                f"Lot #{cmd.lot_id} already has a linked source item demand "
                f"(#{lot.input_demand_id})."
            )

        if lot.source_made_item_id is not None:
            raise SourceItemRequiresReworkStockError(
                f"Lot #{lot.id}'s material source is a rework of made item "
                f"#{lot.source_made_item_id}, demanding it through this flow isn't supported yet."
            )
        if lot.source_bought_item_id is None and lot.source_item_id is None:
            raise LotHasNoMaterialSourceError(f"Lot #{lot.id} has no material source configured.")
        if lot.source_approval_status in (
            SourceApprovalStatus.PENDING,
            SourceApprovalStatus.REJECTED,
        ):
            raise SourceItemApprovalRequiredError(
                f"Lot #{lot.id}'s material source is {lot.source_approval_status.value!r} and must "
                "be approved before it can be demanded."
            )

        project = found_or_raise(
            await self._projects.get_by_id(lot.project_id),
            ProjectNotFoundError,
            f"Project #{lot.project_id} not found.",
        )
        assert_project_active(project)
        assert_whole_pieces(cmd.quantity, what="The demand quantity", unit=cmd.unit)

        demand = build_source_item_demand(
            lot,
            actor,
            quantity=cmd.quantity,
            unit=cmd.unit,
            items_per_unit=cmd.items_per_unit,
            high_priority=cmd.high_priority,
            notify_on_delivery=cmd.notify_on_delivery,
            note=cmd.note,
            desired_delivery_date=cmd.desired_delivery_date,
        )
        saved_demand = await self._demands.save(demand)

        lot.input_demand_id = saved_demand.id
        lot.changed = now_utc()
        lot.changes = append_changelog(
            lot.changes, actor.full_name, f"Linked source item demand #{saved_demand.id}."
        )
        await self._lots.save(lot)

        self._reconciler.touch_demands(
            LifecycleAggregate.SOURCE_DEMANDS, [saved_demand.id], created=True
        )
        await self._reconciler.run(actor, lot.changed)
        await self._uow.commit()

        await recompute_schedule_after_commit(
            self._recompute,
            after=(
                f"creating source item demand "
                f"#{saved_demand.id} for lot #{lot.id}; the demand itself is committed."
            ),
        )

        log.info(f"Created source item demand #{saved_demand.id} for lot {lot.lot_number!r}.")
        return SourceItemDemandMapper.to_result(saved_demand)
