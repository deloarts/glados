"""Use case factories: production lots, lot steps, lot positions."""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.facades import get_made_item_material_sources
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_bought_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_fabrication_method_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_inspection_method_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_made_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_source_item_repo
from src.modules.catalogue.application.facade.made_item_material_source import (
    MadeItemMaterialSources,
)
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IFabricationMethodQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IInspectionMethodQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IMadeItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISourceItemQueries
from src.modules.fulfillment.adapters.inbound.api.deps.lifecycle import get_lifecycle_lock_plan
from src.modules.fulfillment.adapters.inbound.api.deps.lifecycle import get_lifecycle_reconciler
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_recompute_machine_schedule_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_scheduling_repos
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_allocation_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_fulfillment_settings_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_machine_pool_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_made_item_allocation_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_made_item_demand_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_order_item_delivery_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_item_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_lot_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_production_machine_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_production_order_interruption_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_order_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_source_item_allocation_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_source_item_demand_repo,
)
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases._demand_family.unarrived_release import (
    UnarrivedLineRelease,
)
from src.modules.fulfillment.application.use_cases.production_lot.approve_lot_source import (
    ApproveLotSource,
)
from src.modules.fulfillment.application.use_cases.production_lot.assign_external_position import (
    AssignExternalPosition,
)
from src.modules.fulfillment.application.use_cases.production_lot.assign_external_position import (
    UnassignExternalPosition,
)
from src.modules.fulfillment.application.use_cases.production_lot.auto_assign_lots import (
    AutoAssignLots,
)
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.application.use_cases.production_lot.get_lot import GetLot
from src.modules.fulfillment.application.use_cases.production_lot.get_lot import GetLots
from src.modules.fulfillment.application.use_cases.production_lot.get_lot import GetLotsByIds
from src.modules.fulfillment.application.use_cases.production_lot.get_lot_completions import (
    GetLotPositionCompletions,
)
from src.modules.fulfillment.application.use_cases.production_lot.get_lot_demands import (
    GetLotDemands,
)
from src.modules.fulfillment.application.use_cases.production_lot.get_lot_events import GetLotEvents
from src.modules.fulfillment.application.use_cases.production_lot.get_lot_material_receipts import (
    GetLotMaterialReceipts,
)
from src.modules.fulfillment.application.use_cases.production_lot.get_lot_position_balances import (
    GetLotPositionBalances,
)
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CancelLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CompleteLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import HoldLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import ResumeLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_positions import (
    AppendLotPosition,
)
from src.modules.fulfillment.application.use_cases.production_lot.lot_positions import (
    RegroupLotPositions,
)
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import AddLotStep
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import DeleteLotStep
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import ReorderLotSteps
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import UpdateLotStep
from src.modules.fulfillment.application.use_cases.production_lot.record_lot_position_provision import (
    GetLotPositionProvisions,
)
from src.modules.fulfillment.application.use_cases.production_lot.record_lot_position_provision import (
    RecordLotPositionProvision,
)
from src.modules.fulfillment.application.use_cases.production_lot.reject_lot_source import (
    RejectLotSource,
)
from src.modules.fulfillment.application.use_cases.production_lot.replace_structure import (
    ReplaceLotStructure,
)
from src.modules.fulfillment.application.use_cases.production_lot.switch_lot_material_source import (
    SwitchLotMaterialSource,
)
from src.modules.fulfillment.application.use_cases.production_lot.update_lot import UpdateLot
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    IMachinePoolRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemDeliveryRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
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
from src.modules.platform.adapters.inbound.api.deps.database import get_transactional_event_bus
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_project_repo
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries


def get_create_lot_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    made_item_repo: IMadeItemQueries = Depends(get_made_item_repo),
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    allocation_repo: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    source_item_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    inspection_method_repo: IInspectionMethodQueries = Depends(get_inspection_method_repo),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    project_repo: IProjectQueries | None = Depends(get_project_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> CreateLot:
    return CreateLot(
        lot_repo=lot_repo,
        made_item_repo=made_item_repo,
        demand_repo=demand_repo,
        allocation_repo=allocation_repo,
        settings_repo=settings_repo,
        source_item_demand_repo=source_item_demand_repo,
        order_repo=order_repo,
        inspection_method_repo=inspection_method_repo,
        machine_repo=machine_repo,
        uow=uow,
        event_bus=event_bus,
        reconciler=reconciler,
        recompute_schedule=recompute_schedule,
        project_repo=project_repo,
    )


def get_auto_assign_lots_use_case(
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    allocation_repo: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    create_lot: CreateLot = Depends(get_create_lot_use_case),
    project_repo: IProjectQueries | None = Depends(get_project_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> AutoAssignLots:
    return AutoAssignLots(
        demand_repo=demand_repo,
        allocation_repo=allocation_repo,
        lot_repo=lot_repo,
        create_lot=create_lot,
        uow=uow,
        event_bus=event_bus,
        reconciler=reconciler,
        recompute_schedule=recompute_schedule,
        project_repo=project_repo,
    )


def get_update_lot_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    project_repo: IProjectQueries | None = Depends(get_project_repo),
    made_allocation_repo: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
    source_item_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> UpdateLot:
    return UpdateLot(
        lot_repo=lot_repo,
        project_repo=project_repo,
        uow=uow,
        reconciler=reconciler,
        made_allocation_repo=made_allocation_repo,
        source_item_demand_repo=source_item_demand_repo,
        order_item_repo=order_item_repo,
        order_repo=order_repo,
        recompute_schedule=recompute_schedule,
    )


def get_switch_lot_material_source_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    bought_item_repo: IBoughtItemQueries = Depends(get_bought_item_repo),
    source_item_repo: ISourceItemQueries = Depends(get_source_item_repo),
    made_item_repo: IMadeItemQueries = Depends(get_made_item_repo),
    source_item_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    source_item_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    project_repo: IProjectQueries = Depends(get_project_repo),
    bought_allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> SwitchLotMaterialSource:
    return SwitchLotMaterialSource(
        lot_repo=lot_repo,
        bought_item_repo=bought_item_repo,
        source_item_repo=source_item_repo,
        made_item_repo=made_item_repo,
        source_item_demand_repo=source_item_demand_repo,
        source_item_allocation_repo=source_item_allocation_repo,
        settings_repo=settings_repo,
        recompute_schedule=recompute_schedule,
        project_repo=project_repo,
        line_release=UnarrivedLineRelease(
            source_item_allocation_repo,
            LineFillRepos(bought=bought_allocation_repo, source=source_item_allocation_repo),
            order_item_repo,
        ),
        uow=uow,
        reconciler=reconciler,
    )


def get_lot_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    repos: SchedulingRepos = Depends(get_scheduling_repos),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
) -> GetLot:
    return GetLot(lot_repo=lot_repo, repos=repos, machine_repo=machine_repo, pool_repo=pool_repo)


def get_lots_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    repos: SchedulingRepos = Depends(get_scheduling_repos),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
) -> GetLots:
    return GetLots(
        lot_repo=lot_repo,
        repos=repos,
        machine_repo=machine_repo,
        pool_repo=pool_repo,
        settings_repo=settings_repo,
    )


def get_lots_by_ids_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    repos: SchedulingRepos = Depends(get_scheduling_repos),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
) -> GetLotsByIds:
    return GetLotsByIds(
        lot_repo=lot_repo, repos=repos, machine_repo=machine_repo, pool_repo=pool_repo
    )


def get_add_lot_step_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    fabrication_method_repo: IFabricationMethodQueries = Depends(get_fabrication_method_repo),
    inspection_method_repo: IInspectionMethodQueries = Depends(get_inspection_method_repo),
    project_repo: IProjectQueries | None = Depends(get_project_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> AddLotStep:
    return AddLotStep(
        lot_repo=lot_repo,
        fabrication_method_repo=fabrication_method_repo,
        inspection_method_repo=inspection_method_repo,
        project_repo=project_repo,
        uow=uow,
        reconciler=reconciler,
        order_repo=order_repo,
        recompute_schedule=recompute_schedule,
    )


def get_replace_lot_structure_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    fabrication_method_repo: IFabricationMethodQueries = Depends(get_fabrication_method_repo),
    inspection_method_repo: IInspectionMethodQueries = Depends(get_inspection_method_repo),
    project_repo: IProjectQueries | None = Depends(get_project_repo),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> ReplaceLotStructure:
    return ReplaceLotStructure(
        lot_repo=lot_repo,
        fabrication_method_repo=fabrication_method_repo,
        inspection_method_repo=inspection_method_repo,
        project_repo=project_repo,
        order_repo=order_repo,
        recompute_schedule=recompute_schedule,
        order_item_repo=order_item_repo,
        uow=uow,
        reconciler=reconciler,
    )


def get_update_lot_step_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    fabrication_method_repo: IFabricationMethodQueries = Depends(get_fabrication_method_repo),
    inspection_method_repo: IInspectionMethodQueries = Depends(get_inspection_method_repo),
    project_repo: IProjectQueries | None = Depends(get_project_repo),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    lock_plan: LockPlan = Depends(get_lifecycle_lock_plan),
) -> UpdateLotStep:
    return UpdateLotStep(
        lot_repo=lot_repo,
        fabrication_method_repo=fabrication_method_repo,
        inspection_method_repo=inspection_method_repo,
        project_repo=project_repo,
        order_repo=order_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        lock_plan=lock_plan,
    )


def get_delete_lot_step_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    project_repo: IProjectQueries | None = Depends(get_project_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
) -> DeleteLotStep:
    return DeleteLotStep(
        lot_repo=lot_repo,
        project_repo=project_repo,
        order_item_repo=order_item_repo,
        uow=uow,
        reconciler=reconciler,
        recompute_schedule=recompute,
        order_repo=order_repo,
    )


def get_reorder_lot_steps_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> ReorderLotSteps:
    return ReorderLotSteps(
        lot_repo=lot_repo, uow=uow, reconciler=reconciler, recompute_schedule=recompute
    )


def get_regroup_lot_positions_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> RegroupLotPositions:
    return RegroupLotPositions(
        lot_repo=lot_repo,
        order_item_repo=order_item_repo,
        uow=uow,
        reconciler=reconciler,
        recompute_schedule=recompute,
    )


def get_append_lot_position_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    fabrication_method_repo: IFabricationMethodQueries = Depends(get_fabrication_method_repo),
    inspection_method_repo: IInspectionMethodQueries = Depends(get_inspection_method_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> AppendLotPosition:
    return AppendLotPosition(
        lot_repo=lot_repo,
        fabrication_method_repo=fabrication_method_repo,
        inspection_method_repo=inspection_method_repo,
        uow=uow,
        reconciler=reconciler,
    )


def get_assign_external_position_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    made_item_repo: IMadeItemQueries = Depends(get_made_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    project_repo: IProjectQueries = Depends(get_project_repo),
) -> AssignExternalPosition:
    return AssignExternalPosition(
        lot_repo=lot_repo,
        made_item_repo=made_item_repo,
        order_repo=order_repo,
        order_item_repo=order_item_repo,
        project_repo=project_repo,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
        recompute_schedule=recompute_schedule,
    )


def get_unassign_external_position_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> UnassignExternalPosition:
    return UnassignExternalPosition(
        lot_repo=lot_repo,
        order_item_repo=order_item_repo,
        uow=uow,
        reconciler=reconciler,
        recompute_schedule=recompute_schedule,
    )


def get_cancel_lot_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    made_item_allocation_repo: IMadeItemAllocationRepository = Depends(
        get_made_item_allocation_repo
    ),
    source_item_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    source_item_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    interruption_repo: IProductionOrderInterruptionRepository = Depends(
        get_production_order_interruption_repo
    ),
    parent_order_repo: IOrderRepository = Depends(get_order_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    project_repo: IProjectQueries | None = Depends(get_project_repo),
) -> CancelLot:
    return CancelLot(
        lot_repo=lot_repo,
        order_repo=order_repo,
        order_item_repo=order_item_repo,
        allocation_repo=allocation_repo,
        made_item_allocation_repo=made_item_allocation_repo,
        source_item_demand_repo=source_item_demand_repo,
        source_item_allocation_repo=source_item_allocation_repo,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
        interruption_repo=interruption_repo,
        parent_order_repo=parent_order_repo,
        recompute_schedule=recompute_schedule,
        project_repo=project_repo,
    )


def get_complete_lot_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    interruption_repo: IProductionOrderInterruptionRepository = Depends(
        get_production_order_interruption_repo
    ),
    parent_order_repo: IOrderRepository = Depends(get_order_repo),
    made_item_demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    made_item_allocation_repo: IMadeItemAllocationRepository = Depends(
        get_made_item_allocation_repo
    ),
    source_item_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    source_item_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    bought_allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    project_repo: IProjectQueries | None = Depends(get_project_repo),
) -> CompleteLot:
    return CompleteLot(
        lot_repo=lot_repo,
        order_repo=order_repo,
        order_item_repo=order_item_repo,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
        interruption_repo=interruption_repo,
        parent_order_repo=parent_order_repo,
        made_item_demand_repo=made_item_demand_repo,
        made_item_allocation_repo=made_item_allocation_repo,
        source_item_demand_repo=source_item_demand_repo,
        source_item_allocation_repo=source_item_allocation_repo,
        bought_allocation_repo=bought_allocation_repo,
        recompute_schedule=recompute_schedule,
        project_repo=project_repo,
    )


def get_hold_lot_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    interruption_repo: IProductionOrderInterruptionRepository = Depends(
        get_production_order_interruption_repo
    ),
) -> HoldLot:
    return HoldLot(
        lot_repo=lot_repo,
        order_repo=order_repo,
        recompute_schedule=recompute_schedule,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
        interruption_repo=interruption_repo,
    )


def get_resume_lot_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    interruption_repo: IProductionOrderInterruptionRepository = Depends(
        get_production_order_interruption_repo
    ),
) -> ResumeLot:
    return ResumeLot(
        lot_repo=lot_repo,
        order_repo=order_repo,
        recompute_schedule=recompute_schedule,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
        interruption_repo=interruption_repo,
    )


def get_lot_position_completions_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
) -> GetLotPositionCompletions:
    return GetLotPositionCompletions(lot_repo=lot_repo)


def get_lot_events_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
) -> GetLotEvents:
    return GetLotEvents(lot_repo=lot_repo)


def get_lot_demands_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    made_item_allocation_repo: IMadeItemAllocationRepository = Depends(
        get_made_item_allocation_repo
    ),
    made_item_demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
) -> GetLotDemands:
    return GetLotDemands(
        lot_repo=lot_repo,
        made_item_allocation_repo=made_item_allocation_repo,
        made_item_demand_repo=made_item_demand_repo,
    )


def get_record_lot_position_provision_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    lock_plan: LockPlan = Depends(get_lifecycle_lock_plan),
) -> RecordLotPositionProvision:
    return RecordLotPositionProvision(lot_repo=lot_repo, uow=uow, lock_plan=lock_plan)


def get_lot_position_provisions_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
) -> GetLotPositionProvisions:
    return GetLotPositionProvisions(lot_repo=lot_repo)


def get_approve_lot_source_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    source_item_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    source_item_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    made_items: MadeItemMaterialSources = Depends(get_made_item_material_sources),
    source_item_repo: ISourceItemQueries = Depends(get_source_item_repo),
    project_repo: IProjectQueries = Depends(get_project_repo),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> ApproveLotSource:
    return ApproveLotSource(
        lot_repo=lot_repo,
        source_item_demand_repo=source_item_demand_repo,
        source_item_allocation_repo=source_item_allocation_repo,
        made_items=made_items,
        source_item_repo=source_item_repo,
        project_repo=project_repo,
        settings_repo=settings_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        reconciler=reconciler,
    )


def get_reject_lot_source_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    lock_plan: LockPlan = Depends(get_lifecycle_lock_plan),
) -> RejectLotSource:
    return RejectLotSource(lot_repo=lot_repo, uow=uow, lock_plan=lock_plan)


def get_lot_material_receipts_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    source_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    delivery_repo: IOrderItemDeliveryRepository = Depends(get_order_item_delivery_repo),
) -> GetLotMaterialReceipts:
    return GetLotMaterialReceipts(
        lot_repo, source_allocation_repo, order_item_repo, order_repo, delivery_repo
    )


def get_lot_position_balances_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
) -> GetLotPositionBalances:
    return GetLotPositionBalances(lot_repo, order_repo, order_item_repo)
