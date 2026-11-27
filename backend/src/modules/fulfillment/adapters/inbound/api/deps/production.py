"""Use case factories: machines, machine pools, calendars, production orders, schedule, WIP, operators."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_fabrication_method_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_inspection_method_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_made_item_repo
from src.modules.catalogue.ports.outbound.catalogue_queries import IFabricationMethodQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IInspectionMethodQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IMadeItemQueries
from src.modules.fulfillment.adapters.inbound.api.deps.lifecycle import get_lifecycle_lock_plan
from src.modules.fulfillment.adapters.inbound.api.deps.lifecycle import get_lifecycle_reconciler
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_allocation_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_demand_item_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_fulfillment_settings_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_machine_calendar_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_machine_downtime_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_machine_pool_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_made_item_allocation_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_made_item_demand_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_manufacturing_assessment_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_item_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_lot_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_production_machine_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_production_order_file_repo,
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
from src.modules.fulfillment.adapters.inbound.api.deps.services import get_schedule_recompute_lock
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_plan_repository import (
    SqlAlchemyProductionPlanRepository,
)
from src.modules.fulfillment.application.services.lifecycle_actions import LifecycleActions
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.replay_reads import ReplayReads
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.machine_pool.archive_pool import (
    ArchiveMachinePool,
)
from src.modules.fulfillment.application.use_cases.machine_pool.create_pool import CreateMachinePool
from src.modules.fulfillment.application.use_cases.machine_pool.get_pool import GetMachinePool
from src.modules.fulfillment.application.use_cases.machine_pool.get_pool import GetMachinePools
from src.modules.fulfillment.application.use_cases.machine_pool.place_pool import PlaceMachinePool
from src.modules.fulfillment.application.use_cases.machine_pool.restore_pool import (
    RestoreMachinePool,
)
from src.modules.fulfillment.application.use_cases.machine_pool.update_pool import UpdateMachinePool
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.application.use_cases.production_lot.get_planning_exceptions import (
    GetPlanningExceptions,
)
from src.modules.fulfillment.application.use_cases.production_machine.archive_machine import (
    ArchiveProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.calendar_exceptions import (
    CreateMachineCalendarException,
)
from src.modules.fulfillment.application.use_cases.production_machine.calendar_exceptions import (
    DeleteMachineCalendarException,
)
from src.modules.fulfillment.application.use_cases.production_machine.calendar_exceptions import (
    GetMachineCalendarExceptions,
)
from src.modules.fulfillment.application.use_cases.production_machine.calendar_exceptions import (
    UpdateMachineCalendarException,
)
from src.modules.fulfillment.application.use_cases.production_machine.create_machine import (
    CreateProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.downtimes import (
    AddMachineDowntime,
)
from src.modules.fulfillment.application.use_cases.production_machine.downtimes import (
    DeleteMachineDowntime,
)
from src.modules.fulfillment.application.use_cases.production_machine.downtimes import (
    EndMachineDowntime,
)
from src.modules.fulfillment.application.use_cases.production_machine.downtimes import (
    GetMachineDowntimes,
)
from src.modules.fulfillment.application.use_cases.production_machine.downtimes import (
    UpdateMachineDowntime,
)
from src.modules.fulfillment.application.use_cases.production_machine.get_machine import (
    GetProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.get_machine import (
    GetProductionMachines,
)
from src.modules.fulfillment.application.use_cases.production_machine.move_machine import (
    MoveProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.move_machine import (
    PlaceProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.restore_machine import (
    RestoreProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.update_machine import (
    UpdateProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.working_hours import (
    DeleteMachineWorkingHours,
)
from src.modules.fulfillment.application.use_cases.production_machine.working_hours import (
    GetDefaultWorkingHours,
)
from src.modules.fulfillment.application.use_cases.production_machine.working_hours import (
    GetMachineWorkingHours,
)
from src.modules.fulfillment.application.use_cases.production_machine.working_hours import (
    SetDefaultWorkingHours,
)
from src.modules.fulfillment.application.use_cases.production_machine.working_hours import (
    SetMachineWorkingHours,
)
from src.modules.fulfillment.application.use_cases.production_order.assign_internal_position import (
    AssignInternalPosition,
)
from src.modules.fulfillment.application.use_cases.production_order.delete_production_order_file import (
    DeleteProductionOrderFile,
)
from src.modules.fulfillment.application.use_cases.production_order.download_production_order_file import (
    DownloadProductionOrderFile,
)
from src.modules.fulfillment.application.use_cases.production_order.get_manufacturing_assessment import (
    GetManufacturingAssessment,
)
from src.modules.fulfillment.application.use_cases.production_order.get_operators import (
    GetOperators,
)
from src.modules.fulfillment.application.use_cases.production_order.get_order import (
    GetProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.get_order import (
    GetProductionOrders,
)
from src.modules.fulfillment.application.use_cases.production_order.get_production_order_files import (
    GetProductionOrderFiles,
)
from src.modules.fulfillment.application.use_cases.production_order.get_production_wip import (
    GetProductionWip,
)
from src.modules.fulfillment.application.use_cases.production_order.get_qa_tasks import GetQaTasks
from src.modules.fulfillment.application.use_cases.production_order.identify_operator_by_rfid import (
    IdentifyOperatorByRfid,
)
from src.modules.fulfillment.application.use_cases.production_order.merge_production_orders import (
    MergeProductionOrders,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    CancelProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    PauseProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    StartProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.reassign_production_order_machine import (
    ReassignProductionOrderMachine,
)
from src.modules.fulfillment.application.use_cases.production_order.record_manufacturing_assessment import (
    RecordManufacturingAssessment,
)
from src.modules.fulfillment.application.use_cases.production_order.record_production_order_completion import (
    RecordProductionOrderCompletion,
)
from src.modules.fulfillment.application.use_cases.production_order.reorder_production_orders import (
    ReorderProductionOrders,
)
from src.modules.fulfillment.application.use_cases.production_order.reverse_production_order_completion import (
    ReverseProductionOrderCompletion,
)
from src.modules.fulfillment.application.use_cases.production_order.scrap_lot_pieces import (
    ScrapLotPieces,
)
from src.modules.fulfillment.application.use_cases.production_order.scrap_production_pieces import (
    ScrapProductionPieces,
)
from src.modules.fulfillment.application.use_cases.production_order.split_production_order import (
    SplitProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.update_production_order import (
    UpdateProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.update_production_order_file import (
    UpdateProductionOrderFile,
)
from src.modules.fulfillment.application.use_cases.production_order.upload_production_order_file import (
    UploadProductionOrderFile,
)
from src.modules.fulfillment.application.use_cases.production_plan.purge_expired_plans import (
    PurgeExpiredPlans,
)
from src.modules.fulfillment.application.use_cases.production_plan.record_plan_baseline import (
    RecordPlanBaseline,
)
from src.modules.fulfillment.application.use_cases.production_schedule.auto_plan import AutoPlan
from src.modules.fulfillment.application.use_cases.production_schedule.get_schedule_board import (
    GetScheduleBoard,
)
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_calendar_repository import (
    IMachineCalendarRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_downtime_repository import (
    IMachineDowntimeRepository,
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
from src.modules.fulfillment.ports.outbound.repositories.manufacturing_assessment_repository import (
    IManufacturingAssessmentRepository,
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
from src.modules.fulfillment.ports.outbound.schedule_recompute_generation_port import (
    IScheduleRecomputeGenerationCounter,
)
from src.modules.fulfillment.ports.outbound.schedule_recompute_lock_port import (
    IScheduleRecomputeLock,
)
from src.modules.platform.adapters.inbound.api.deps.bindings import (
    get_schedule_recompute_generation_counter,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_db
from src.modules.platform.adapters.inbound.api.deps.database import get_transactional_event_bus
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_repo
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_storage_adapter
from src.modules.platform.adapters.outbound.persistence.lost_race import lost_race
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_project_repo
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries


def get_scheduling_repos(
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    source_item_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    source_item_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    made_item_allocation_repo: IMadeItemAllocationRepository = Depends(
        get_made_item_allocation_repo
    ),
    made_item_demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
) -> SchedulingRepos:
    return SchedulingRepos(
        orders=order_repo,
        lots=lot_repo,
        order_items=order_item_repo,
        source_item_demands=source_item_demand_repo,
        source_item_allocations=source_item_allocation_repo,
        made_item_allocations=made_item_allocation_repo,
        made_item_demands=made_item_demand_repo,
        settings=settings_repo,
    )


def get_recompute_machine_schedule_use_case(
    repos: SchedulingRepos = Depends(get_scheduling_repos),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    calendar_repo: IMachineCalendarRepository = Depends(get_machine_calendar_repo),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
    downtime_repo: IMachineDowntimeRepository = Depends(get_machine_downtime_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    generation_counter: IScheduleRecomputeGenerationCounter = Depends(
        get_schedule_recompute_generation_counter
    ),
    recompute_lock: IScheduleRecomputeLock = Depends(get_schedule_recompute_lock),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
) -> RecomputeMachineSchedule:
    """The recompute a write runs after its commit, which in the app only
    requests the walk (cfg.scheduling.recompute_in_background)."""
    return RecomputeMachineSchedule(
        repos=repos,
        machine_repo=machine_repo,
        calendar_repo=calendar_repo,
        settings_repo=settings_repo,
        pool_repo=pool_repo,
        downtime_repo=downtime_repo,
        uow=uow,
        generation_counter=generation_counter,
        recompute_lock=recompute_lock,
        event_bus=event_bus,
        defer=cfg.scheduling.recompute_in_background,
    )


def get_schedule_board_use_case(
    repos: SchedulingRepos = Depends(get_scheduling_repos),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    calendar_repo: IMachineCalendarRepository = Depends(get_machine_calendar_repo),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
    downtime_repo: IMachineDowntimeRepository = Depends(get_machine_downtime_repo),
    generation_counter: IScheduleRecomputeGenerationCounter = Depends(
        get_schedule_recompute_generation_counter
    ),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> GetScheduleBoard:
    return GetScheduleBoard(
        repos=repos,
        machine_repo=machine_repo,
        calendar_repo=calendar_repo,
        settings_repo=settings_repo,
        pool_repo=pool_repo,
        downtime_repo=downtime_repo,
        generation_counter=generation_counter,
        uow=uow,
    )


def _scheduling_repos(db: AsyncSession) -> SchedulingRepos:
    return get_scheduling_repos(
        order_repo=get_production_order_repo(db),
        lot_repo=get_production_lot_repo(db),
        order_item_repo=get_order_item_repo(db),
        source_item_demand_repo=get_source_item_demand_repo(db),
        source_item_allocation_repo=get_source_item_allocation_repo(db),
        made_item_allocation_repo=get_made_item_allocation_repo(db),
        made_item_demand_repo=get_made_item_demand_repo(db),
        settings_repo=get_fulfillment_settings_repo(db),
    )


def build_requested_schedule_walk(
    db: AsyncSession, generation_counter: IScheduleRecomputeGenerationCounter
) -> RecomputeMachineSchedule:
    """The walk a write below Planning & fulfillment requests after its
    commit, built on the request's session and generation counter exactly
    like get_recompute_machine_schedule_use_case. The composition root binds
    it to Platform's get_schedule_recompute."""
    return get_recompute_machine_schedule_use_case(
        repos=_scheduling_repos(db),
        machine_repo=get_production_machine_repo(db),
        calendar_repo=get_machine_calendar_repo(db),
        settings_repo=get_fulfillment_settings_repo(db),
        pool_repo=get_machine_pool_repo(db),
        downtime_repo=get_machine_downtime_repo(db),
        uow=get_unit_of_work(db),
        generation_counter=generation_counter,
        recompute_lock=get_schedule_recompute_lock(),
        event_bus=get_transactional_event_bus(db),
    )


def build_schedule_walk(db: AsyncSession) -> RecomputeMachineSchedule:
    """The schedule walk on one session, which walks when called instead of
    requesting a walk: Auto-Plan's own, the `schedule` event worker's and
    the periodic tick's."""
    return RecomputeMachineSchedule(
        repos=_scheduling_repos(db),
        machine_repo=get_production_machine_repo(db),
        calendar_repo=get_machine_calendar_repo(db),
        settings_repo=get_fulfillment_settings_repo(db),
        pool_repo=get_machine_pool_repo(db),
        downtime_repo=get_machine_downtime_repo(db),
        uow=get_unit_of_work(db),
        generation_counter=get_schedule_recompute_generation_counter(),
        recompute_lock=get_schedule_recompute_lock(),
    )


def build_auto_plan_use_case(db: AsyncSession) -> AutoPlan:
    """Composition root for `AutoPlan`, built from a single DB session: the
    single source of truth both `get_auto_plan_use_case` below (FastAPI
    `Depends` chain, request-scoped session) and the `/auto-plan/stream`
    endpoint's background worker (its own `SessionLocal()`, opened outside any
    request scope, see endpoints/production_schedule.py) build the use
    case from, so the two entry points can never drift.

    Calls the very same provider functions the `Depends` graph below uses
    (`get_scheduling_repos`, `get_recompute_machine_schedule_use_case`,
    every `get_*_repo` and `get_unit_of_work`), passing `db`
    explicitly instead of letting FastAPI resolve it. These are plain
    functions with `Depends(...)` defaults, so calling them directly like
    this is ordinary Python, not framework magic. This mirrors the exact
    constructor arguments without duplicating a single one of them."""
    repos = _scheduling_repos(db)
    machine_repo = get_production_machine_repo(db)
    calendar_repo = get_machine_calendar_repo(db)
    settings_repo = get_fulfillment_settings_repo(db)
    pool_repo = get_machine_pool_repo(db)
    downtime_repo = get_machine_downtime_repo(db)
    uow = get_unit_of_work(db)
    # Auto-Plan walks in the request, since its answer is the plan.
    recompute_schedule = build_schedule_walk(db)
    return AutoPlan(
        repos=repos,
        machine_repo=machine_repo,
        calendar_repo=calendar_repo,
        settings_repo=settings_repo,
        recompute_schedule=recompute_schedule,
        pool_repo=pool_repo,
        downtime_repo=downtime_repo,
        uow=uow,
        retryable=lost_race,
    )


def get_auto_plan_use_case(db: AsyncSession = Depends(get_db, scope="function")) -> AutoPlan:
    return build_auto_plan_use_case(db)


def get_create_production_machine_use_case(
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    fabrication_method_repo: IFabricationMethodQueries = Depends(get_fabrication_method_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateProductionMachine:
    return CreateProductionMachine(
        machine_repo=machine_repo,
        fabrication_method_repo=fabrication_method_repo,
        event_bus=event_bus,
        uow=uow,
    )


def get_update_production_machine_use_case(
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    fabrication_method_repo: IFabricationMethodQueries = Depends(get_fabrication_method_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> UpdateProductionMachine:
    return UpdateProductionMachine(
        machine_repo=machine_repo,
        fabrication_method_repo=fabrication_method_repo,
        event_bus=event_bus,
        uow=uow,
        recompute_schedule=recompute,
    )


def get_archive_production_machine_use_case(
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
) -> ArchiveProductionMachine:
    return ArchiveProductionMachine(
        machine_repo=machine_repo,
        order_repo=order_repo,
        event_bus=event_bus,
        uow=uow,
        recompute_schedule=recompute,
    )


def get_move_production_machine_use_case(
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> MoveProductionMachine:
    return MoveProductionMachine(machine_repo=machine_repo, uow=uow)


def get_place_production_machine_use_case(
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> PlaceProductionMachine:
    return PlaceProductionMachine(machine_repo=machine_repo, uow=uow)


def get_restore_production_machine_use_case(
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> RestoreProductionMachine:
    return RestoreProductionMachine(
        machine_repo=machine_repo, event_bus=event_bus, uow=uow, recompute_schedule=recompute
    )


def get_production_machine_use_case(
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    downtime_repo: IMachineDowntimeRepository = Depends(get_machine_downtime_repo),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
) -> GetProductionMachine:
    return GetProductionMachine(
        machine_repo=machine_repo, downtime_repo=downtime_repo, order_repo=order_repo
    )


def get_production_machines_use_case(
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    downtime_repo: IMachineDowntimeRepository = Depends(get_machine_downtime_repo),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
) -> GetProductionMachines:
    return GetProductionMachines(
        machine_repo=machine_repo, downtime_repo=downtime_repo, order_repo=order_repo
    )


def get_create_machine_pool_use_case(
    machine_pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
    production_machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateMachinePool:
    return CreateMachinePool(
        machine_pool_repo=machine_pool_repo,
        production_machine_repo=production_machine_repo,
        event_bus=event_bus,
        uow=uow,
    )


def get_update_machine_pool_use_case(
    machine_pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
    production_machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> UpdateMachinePool:
    return UpdateMachinePool(
        machine_pool_repo=machine_pool_repo,
        production_machine_repo=production_machine_repo,
        event_bus=event_bus,
        uow=uow,
        recompute_schedule=recompute,
    )


def get_archive_machine_pool_use_case(
    machine_pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> ArchiveMachinePool:
    return ArchiveMachinePool(
        machine_pool_repo=machine_pool_repo,
        event_bus=event_bus,
        uow=uow,
        recompute_schedule=recompute,
    )


def get_restore_machine_pool_use_case(
    machine_pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> RestoreMachinePool:
    return RestoreMachinePool(
        machine_pool_repo=machine_pool_repo,
        event_bus=event_bus,
        uow=uow,
        recompute_schedule=recompute,
    )


def get_machine_pool_use_case(
    machine_pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
) -> GetMachinePool:
    return GetMachinePool(machine_pool_repo=machine_pool_repo)


def get_machine_pools_use_case(
    machine_pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
) -> GetMachinePools:
    return GetMachinePools(machine_pool_repo=machine_pool_repo)


def get_machine_working_hours_use_case(
    calendar_repo: IMachineCalendarRepository = Depends(get_machine_calendar_repo),
) -> GetMachineWorkingHours:
    return GetMachineWorkingHours(calendar_repo=calendar_repo)


def get_default_working_hours_use_case(
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
) -> GetDefaultWorkingHours:
    return GetDefaultWorkingHours(settings_repo=settings_repo)


def get_set_default_working_hours_use_case(
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> SetDefaultWorkingHours:
    return SetDefaultWorkingHours(
        settings_repo=settings_repo, uow=uow, recompute_schedule=recompute
    )


def get_set_machine_working_hours_use_case(
    calendar_repo: IMachineCalendarRepository = Depends(get_machine_calendar_repo),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> SetMachineWorkingHours:
    return SetMachineWorkingHours(
        calendar_repo=calendar_repo,
        machine_repo=machine_repo,
        uow=uow,
        recompute_schedule=recompute,
    )


def get_delete_machine_working_hours_use_case(
    calendar_repo: IMachineCalendarRepository = Depends(get_machine_calendar_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> DeleteMachineWorkingHours:
    return DeleteMachineWorkingHours(
        calendar_repo=calendar_repo, uow=uow, recompute_schedule=recompute
    )


def get_machine_calendar_exceptions_use_case(
    calendar_repo: IMachineCalendarRepository = Depends(get_machine_calendar_repo),
) -> GetMachineCalendarExceptions:
    return GetMachineCalendarExceptions(calendar_repo=calendar_repo)


def get_create_machine_calendar_exception_use_case(
    calendar_repo: IMachineCalendarRepository = Depends(get_machine_calendar_repo),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> CreateMachineCalendarException:
    return CreateMachineCalendarException(
        calendar_repo=calendar_repo,
        machine_repo=machine_repo,
        uow=uow,
        recompute_schedule=recompute,
    )


def get_update_machine_calendar_exception_use_case(
    calendar_repo: IMachineCalendarRepository = Depends(get_machine_calendar_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> UpdateMachineCalendarException:
    return UpdateMachineCalendarException(
        calendar_repo=calendar_repo, uow=uow, recompute_schedule=recompute
    )


def get_delete_machine_calendar_exception_use_case(
    calendar_repo: IMachineCalendarRepository = Depends(get_machine_calendar_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> DeleteMachineCalendarException:
    return DeleteMachineCalendarException(
        calendar_repo=calendar_repo, uow=uow, recompute_schedule=recompute
    )


# ── Machine downtime ────────────────────────────────────────────────────


def get_machine_downtimes_use_case(
    downtime_repo: IMachineDowntimeRepository = Depends(get_machine_downtime_repo),
) -> GetMachineDowntimes:
    return GetMachineDowntimes(downtime_repo=downtime_repo)


def get_add_machine_downtime_use_case(
    downtime_repo: IMachineDowntimeRepository = Depends(get_machine_downtime_repo),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> AddMachineDowntime:
    return AddMachineDowntime(
        downtime_repo=downtime_repo,
        machine_repo=machine_repo,
        event_bus=event_bus,
        uow=uow,
        recompute_schedule=recompute,
    )


def get_end_machine_downtime_use_case(
    downtime_repo: IMachineDowntimeRepository = Depends(get_machine_downtime_repo),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> EndMachineDowntime:
    return EndMachineDowntime(
        downtime_repo=downtime_repo,
        machine_repo=machine_repo,
        event_bus=event_bus,
        uow=uow,
        recompute_schedule=recompute,
    )


def get_update_machine_downtime_use_case(
    downtime_repo: IMachineDowntimeRepository = Depends(get_machine_downtime_repo),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> UpdateMachineDowntime:
    return UpdateMachineDowntime(
        downtime_repo=downtime_repo,
        machine_repo=machine_repo,
        event_bus=event_bus,
        uow=uow,
        recompute_schedule=recompute,
    )


def get_delete_machine_downtime_use_case(
    downtime_repo: IMachineDowntimeRepository = Depends(get_machine_downtime_repo),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> DeleteMachineDowntime:
    return DeleteMachineDowntime(
        downtime_repo=downtime_repo,
        machine_repo=machine_repo,
        event_bus=event_bus,
        uow=uow,
        recompute_schedule=recompute,
    )


def get_production_order_use_case(
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    repos: SchedulingRepos = Depends(get_scheduling_repos),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
) -> GetProductionOrder:
    return GetProductionOrder(
        order_repo=order_repo, repos=repos, machine_repo=machine_repo, pool_repo=pool_repo
    )


def get_production_orders_use_case(
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    repos: SchedulingRepos = Depends(get_scheduling_repos),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
) -> GetProductionOrders:
    return GetProductionOrders(
        order_repo=order_repo, repos=repos, machine_repo=machine_repo, pool_repo=pool_repo
    )


def get_update_production_order_use_case(
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    calendar_repo: IMachineCalendarRepository = Depends(get_machine_calendar_repo),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    lock_plan: LockPlan = Depends(get_lifecycle_lock_plan),
) -> UpdateProductionOrder:
    return UpdateProductionOrder(
        order_repo=order_repo,
        recompute_schedule=recompute_schedule,
        calendar_repo=calendar_repo,
        settings_repo=settings_repo,
        uow=uow,
        lock_plan=lock_plan,
    )


def get_assign_internal_position_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    project_repo: IProjectQueries | None = Depends(get_project_repo),
    pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> AssignInternalPosition:
    return AssignInternalPosition(
        lot_repo=lot_repo,
        machine_repo=machine_repo,
        order_repo=order_repo,
        settings_repo=settings_repo,
        recompute_schedule=recompute_schedule,
        project_repo=project_repo,
        pool_repo=pool_repo,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
    )


def get_split_production_order_use_case(
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> SplitProductionOrder:
    return SplitProductionOrder(
        order_repo=order_repo,
        lot_repo=lot_repo,
        settings_repo=settings_repo,
        recompute_schedule=recompute_schedule,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
    )


def get_merge_production_orders_use_case(
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> MergeProductionOrders:
    return MergeProductionOrders(
        order_repo=order_repo,
        lot_repo=lot_repo,
        recompute_schedule=recompute_schedule,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
    )


def get_reorder_production_orders_use_case(
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    lock_plan: LockPlan = Depends(get_lifecycle_lock_plan),
) -> ReorderProductionOrders:
    return ReorderProductionOrders(
        order_repo=order_repo,
        recompute_schedule=recompute_schedule,
        event_bus=event_bus,
        uow=uow,
        lock_plan=lock_plan,
    )


def get_reassign_production_order_machine_use_case(
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
    lock_plan: LockPlan = Depends(get_lifecycle_lock_plan),
) -> ReassignProductionOrderMachine:
    return ReassignProductionOrderMachine(
        order_repo=order_repo,
        lot_repo=lot_repo,
        machine_repo=machine_repo,
        event_bus=event_bus,
        uow=uow,
        recompute_schedule=recompute_schedule,
        pool_repo=pool_repo,
        lock_plan=lock_plan,
    )


def get_start_production_order_use_case(
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    project_repo: IProjectQueries | None = Depends(get_project_repo),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
    interruption_repo: IProductionOrderInterruptionRepository = Depends(
        get_production_order_interruption_repo
    ),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> StartProductionOrder:
    return StartProductionOrder(
        order_repo=order_repo,
        lot_repo=lot_repo,
        event_bus=event_bus,
        uow=uow,
        project_repo=project_repo,
        machine_repo=machine_repo,
        pool_repo=pool_repo,
        interruption_repo=interruption_repo,
        reconciler=reconciler,
        recompute_schedule=recompute_schedule,
    )


def get_pause_production_order_use_case(
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    project_repo: IProjectQueries | None = Depends(get_project_repo),
    interruption_repo: IProductionOrderInterruptionRepository = Depends(
        get_production_order_interruption_repo
    ),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> PauseProductionOrder:
    return PauseProductionOrder(
        order_repo=order_repo,
        lot_repo=lot_repo,
        event_bus=event_bus,
        uow=uow,
        project_repo=project_repo,
        interruption_repo=interruption_repo,
        reconciler=reconciler,
        recompute_schedule=recompute_schedule,
    )


def get_cancel_production_order_use_case(
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    project_repo: IProjectQueries | None = Depends(get_project_repo),
    interruption_repo: IProductionOrderInterruptionRepository = Depends(
        get_production_order_interruption_repo
    ),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> CancelProductionOrder:
    return CancelProductionOrder(
        order_repo=order_repo,
        lot_repo=lot_repo,
        event_bus=event_bus,
        uow=uow,
        project_repo=project_repo,
        interruption_repo=interruption_repo,
        reconciler=reconciler,
        recompute_schedule=recompute_schedule,
    )


def get_create_lot_for_completion_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    made_item_repo: IMadeItemQueries = Depends(get_made_item_repo),
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    allocation_repo: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    source_item_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    inspection_method_repo: IInspectionMethodQueries = Depends(get_inspection_method_repo),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> CreateLot:
    """A second CreateLot wiring, separate from deps/lots.py's own
    get_create_lot_use_case: RecordProductionOrderCompletion's disposition
    flow needs create_no_commit() folded into ITS transaction (same
    `uow`/db-session instance, cached per-request by FastAPI's Depends),
    not a self-committing CreateLot.execute() call like AutoAssignLots
    uses. Importing deps/lots.py directly here would also be circular;
    it already imports from this module. The reconciler is the request's
    one, which the disposition's caller runs."""
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
    )


def get_scrap_production_pieces_use_case(
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    made_item_demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    made_item_allocation_repo: IMadeItemAllocationRepository = Depends(
        get_made_item_allocation_repo
    ),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    create_lot: CreateLot = Depends(get_create_lot_for_completion_use_case),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    parent_order_repo: IOrderRepository = Depends(get_order_repo),
    interruption_repo: IProductionOrderInterruptionRepository = Depends(
        get_production_order_interruption_repo
    ),
    source_item_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    source_item_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    bought_allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    project_repo: IProjectQueries | None = Depends(get_project_repo),
) -> ScrapProductionPieces:
    return ScrapProductionPieces(
        order_repo=order_repo,
        lot_repo=lot_repo,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
        order_item_repo=order_item_repo,
        parent_order_repo=parent_order_repo,
        interruption_repo=interruption_repo,
        source_item_demand_repo=source_item_demand_repo,
        source_item_allocation_repo=source_item_allocation_repo,
        bought_allocation_repo=bought_allocation_repo,
        made_item_demand_repo=made_item_demand_repo,
        made_item_allocation_repo=made_item_allocation_repo,
        recompute_schedule=recompute_schedule,
        create_lot=create_lot,
        settings_repo=settings_repo,
        project_repo=project_repo,
    )


def get_scrap_lot_pieces_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    scrap_production_pieces: ScrapProductionPieces = Depends(get_scrap_production_pieces_use_case),
) -> ScrapLotPieces:
    return ScrapLotPieces(
        lot_repo=lot_repo,
        order_repo=order_repo,
        scrap_production_pieces=scrap_production_pieces,
    )


def get_reverse_production_order_completion_use_case(
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> ReverseProductionOrderCompletion:
    return ReverseProductionOrderCompletion(
        order_repo,
        lot_repo,
        order_item_repo,
        settings_repo,
        uow=uow,
        event_bus=event_bus,
        reconciler=reconciler,
        recompute_schedule=recompute_schedule,
    )


def get_record_production_order_completion_use_case(
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    file_repo: IProductionOrderFileRepository = Depends(get_production_order_file_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    made_item_demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    made_item_allocation_repo: IMadeItemAllocationRepository = Depends(
        get_made_item_allocation_repo
    ),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    create_lot: CreateLot = Depends(get_create_lot_for_completion_use_case),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    parent_order_repo: IOrderRepository = Depends(get_order_repo),
    interruption_repo: IProductionOrderInterruptionRepository = Depends(
        get_production_order_interruption_repo
    ),
    source_item_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    source_item_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    bought_allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    project_repo: IProjectQueries | None = Depends(get_project_repo),
) -> RecordProductionOrderCompletion:
    return RecordProductionOrderCompletion(
        order_repo=order_repo,
        lot_repo=lot_repo,
        file_repo=file_repo,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
        made_item_demand_repo=made_item_demand_repo,
        made_item_allocation_repo=made_item_allocation_repo,
        recompute_schedule=recompute_schedule,
        create_lot=create_lot,
        order_item_repo=order_item_repo,
        parent_order_repo=parent_order_repo,
        interruption_repo=interruption_repo,
        source_item_demand_repo=source_item_demand_repo,
        source_item_allocation_repo=source_item_allocation_repo,
        bought_allocation_repo=bought_allocation_repo,
        settings_repo=settings_repo,
        project_repo=project_repo,
    )


def get_production_order_files_use_case(
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    file_repo: IProductionOrderFileRepository = Depends(get_production_order_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
) -> GetProductionOrderFiles:
    return GetProductionOrderFiles(order_repo=order_repo, file_repo=file_repo, storage=storage)


def get_upload_production_order_file_use_case(
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    file_repo: IProductionOrderFileRepository = Depends(get_production_order_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UploadProductionOrderFile:
    return UploadProductionOrderFile(
        order_repo=order_repo, file_repo=file_repo, storage=storage, uow=uow
    )


def get_update_production_order_file_use_case(
    file_repo: IProductionOrderFileRepository = Depends(get_production_order_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateProductionOrderFile:
    return UpdateProductionOrderFile(file_repo=file_repo, storage=storage, uow=uow)


def get_delete_production_order_file_use_case(
    file_repo: IProductionOrderFileRepository = Depends(get_production_order_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DeleteProductionOrderFile:
    return DeleteProductionOrderFile(
        file_repo=file_repo, storage=storage, order_repo=order_repo, uow=uow
    )


def get_download_production_order_file_use_case(
    file_repo: IProductionOrderFileRepository = Depends(get_production_order_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DownloadProductionOrderFile:
    return DownloadProductionOrderFile(file_repo=file_repo, storage=storage, uow=uow)


def get_record_manufacturing_assessment_use_case(
    assessment_repo: IManufacturingAssessmentRepository = Depends(
        get_manufacturing_assessment_repo
    ),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RecordManufacturingAssessment:
    return RecordManufacturingAssessment(
        assessment_repo=assessment_repo, order_repo=order_repo, event_bus=event_bus, uow=uow
    )


def get_manufacturing_assessment_use_case(
    assessment_repo: IManufacturingAssessmentRepository = Depends(
        get_manufacturing_assessment_repo
    ),
) -> GetManufacturingAssessment:
    return GetManufacturingAssessment(assessment_repo=assessment_repo)


def get_operators_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
) -> GetOperators:
    return GetOperators(user_repo=user_repo)


def get_identify_operator_by_rfid_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
) -> IdentifyOperatorByRfid:
    return IdentifyOperatorByRfid(user_repo=user_repo, settings_repo=settings_repo)


def get_production_wip_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
) -> GetProductionWip:
    return GetProductionWip(lot_repo=lot_repo)


def get_planning_exceptions_use_case(
    repos: SchedulingRepos = Depends(get_scheduling_repos),
    bought_demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    bought_allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
) -> GetPlanningExceptions:
    return GetPlanningExceptions(
        repos,
        bought_demand_repo=bought_demand_repo,
        bought_allocation_repo=bought_allocation_repo,
        order_repo=order_repo,
    )


def get_qa_tasks_use_case(
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    file_repo: IProductionOrderFileRepository = Depends(get_production_order_file_repo),
    repos: SchedulingRepos = Depends(get_scheduling_repos),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
) -> GetQaTasks:
    return GetQaTasks(
        order_repo=order_repo,
        lot_repo=lot_repo,
        machine_repo=machine_repo,
        file_repo=file_repo,
        repos=repos,
        storage=storage,
    )


def get_replay_reads(
    production_order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
) -> ReplayReads:
    """Reads the answers of the idempotent production routes back."""
    return ReplayReads(production_order_repo, lot_repo)


def get_lifecycle_actions(
    order_repo: IOrderRepository = Depends(get_order_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    production_order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    repos: SchedulingRepos = Depends(get_scheduling_repos),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
    bought_allocations: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    made_allocations: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
    source_allocations: ISourceItemAllocationRepository = Depends(get_source_item_allocation_repo),
) -> LifecycleActions:
    """Fills the lifecycle actions of the results an endpoint returns."""
    return LifecycleActions(
        order_repo=order_repo,
        lot_repo=lot_repo,
        production_order_repo=production_order_repo,
        scheduling=repos,
        machine_repo=machine_repo,
        pool_repo=pool_repo,
        bought_allocations=bought_allocations,
        made_allocations=made_allocations,
        source_allocations=source_allocations,
    )


def get_place_machine_pool_use_case(
    machine_pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> PlaceMachinePool:
    return PlaceMachinePool(machine_pool_repo=machine_pool_repo, uow=uow)


def build_record_plan_baseline(db: AsyncSession) -> RecordPlanBaseline:
    """The nightly baseline on one session, for the background job that
    records it."""
    return RecordPlanBaseline(
        SqlAlchemyProductionPlanRepository(db),
        _scheduling_repos(db),
        get_machine_calendar_repo(db),
        uow=get_unit_of_work(db),
    )


def build_purge_expired_plans(db: AsyncSession) -> PurgeExpiredPlans:
    """The purge of expired plans on one session, run with the baseline."""
    return PurgeExpiredPlans(
        SqlAlchemyProductionPlanRepository(db),
        get_fulfillment_settings_repo(db),
        uow=get_unit_of_work(db),
    )
