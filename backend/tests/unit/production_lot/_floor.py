"""
A shop floor over in-memory fakes for tests that drive a lot through several
use cases: a lot created by the real CreateLot from a made item with one
fabrication process per position, production orders seeded on its
positions with the facts their statuses stand for, and the completion and
scrap use cases over the same fakes, each call with a lifecycle reconciler
of its own, as one request after another would use them.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.production_lot_dto import CreateLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import LotDemandAllocationInput
from src.modules.fulfillment.application.dto.production_order_dto import (
    RecordProductionOrderCompletionCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    ScrapProductionPiecesCommand,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.application.use_cases.production_order.record_production_order_completion import (
    RecordProductionOrderCompletion,
)
from src.modules.fulfillment.application.use_cases.production_order.scrap_production_pieces import (
    ScrapProductionPieces,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit._tenant_settings import TenantSettings
from tests.unit.production_lot._helpers import make_demand
from tests.unit.production_lot._helpers import make_inspection_method
from tests.unit.production_lot._helpers import make_made_item
from tests.unit.production_lot._helpers import make_process
from tests.unit.production_lot._helpers import make_production_order
from tests.unit.production_lot.fakes import FakeAdminSettingsRepository
from tests.unit.production_lot.fakes import FakeBoughtItemAllocationRepository
from tests.unit.production_lot.fakes import FakeEventBus
from tests.unit.production_lot.fakes import FakeInspectionMethodRepository
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeMadeItemRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeOrderRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionMachineRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_lot.fakes import lot_reconciler
from tests.unit.production_order.fakes import FakeProductionOrderInterruptionRepository
from tests.unit.production_order.fakes import FakeProductionOrderRepository

NOW = datetime(2026, 1, 2, tzinfo=UTC)
TODAY = date(2026, 1, 2)


class Floor:
    def __init__(self, positions: int = 3, *, inspection_last: bool = False) -> None:
        """`positions` positions of one fabrication step each; with
        `inspection_last` the last one is an inspection instead."""
        self.lots = FakeProductionLotRepository()
        self.orders = FakeProductionOrderRepository()
        self.lots.production_orders = self.orders._orders
        self.made_demands = FakeMadeItemDemandRepository()
        self.made_allocations = FakeMadeItemAllocationRepository()
        self.source_demands = FakeSourceItemDemandRepository()
        self.source_allocations = FakeSourceItemAllocationRepository()
        self.order_items = FakeOrderItemRepository()
        self.parent_orders = FakeOrderRepository([])
        self.interruptions = FakeProductionOrderInterruptionRepository(self.orders._orders)
        self.bought_allocations = FakeBoughtItemAllocationRepository()
        self.uow = FakeUnitOfWork()
        self.bus = FakeEventBus()
        self.planner = make_user(id=1, permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
        self.operator = make_user(
            id=3, permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.WRITE_INSPECTIONS]
        )
        processes = [
            make_process(id=i, position=i - 1, fabrication_method_id=1)
            for i in range(1, positions + 1)
        ]
        if inspection_last:
            processes[-1] = make_process(
                id=positions,
                position=positions - 1,
                fabrication_method_id=None,
                role=StepRole.INSPECTION,
                inspection_method_id=1,
            )
        self.made_items = FakeMadeItemRepository([make_made_item(processes=processes)])
        self.inspection_methods = FakeInspectionMethodRepository([make_inspection_method(id=1)])

    def request(self) -> tuple[LifecycleReconciler, CreateLot]:
        """The reconciler of one request and the CreateLot it shares with
        the use case that spawns follow-up lots."""
        reconciler = lot_reconciler(
            self.lots,
            self.orders,
            bus=self.bus,
            made_demands=self.made_demands,
            made_allocations=self.made_allocations,
            source_demands=self.source_demands,
            source_allocations=self.source_allocations,
        )
        create_lot = CreateLot(
            lot_repo=self.lots,
            made_item_repo=self.made_items,
            demand_repo=self.made_demands,
            allocation_repo=self.made_allocations,
            settings_repo=FakeAdminSettingsRepository(require_qa=False),
            source_item_demand_repo=self.source_demands,
            order_repo=self.orders,
            inspection_method_repo=self.inspection_methods,
            machine_repo=FakeProductionMachineRepository(),
            uow=self.uow,
            event_bus=FakeEventBus(),
            reconciler=reconciler,
        )
        return reconciler, create_lot

    async def lot(
        self,
        quantity: float = 10.0,
        demands: list[tuple[int, float, MadeItemDemandStatus]] | None = None,
        raw_material: float | None = None,
    ) -> ProductionLot:
        """A lot of `quantity` whose raw material has arrived, all of it
        unless `raw_material` says how much, covering the made demands given
        as (id, allocated, status)."""
        allocations = []
        for demand_id, allocated, status in demands or []:
            await self.made_demands.save(
                make_demand(id=demand_id, quantity=allocated, status=status)
            )
            allocations.append(
                LotDemandAllocationInput(demand_item_id=demand_id, quantity=allocated)
            )
        _, create_lot = self.request()
        result = await create_lot.execute(
            self.planner,
            CreateLotCommand(
                made_item_id=1,
                project_id=1,
                quantity=quantity,
                demand_allocations=allocations,
            ),
        )
        lot = await self.reload(result.id)
        lot.input_demand_id = 900 + lot.id
        self.lots._raw_material_arrived_by_demand[lot.input_demand_id] = (
            quantity if raw_material is None else raw_material
        )
        await self.lots.save(lot)
        return lot

    async def reload(self, lot_id: int) -> ProductionLot:
        lot = await self.lots.get_by_id(lot_id)
        assert lot is not None
        return lot

    async def positions(self, lot_id: int) -> list[LotPosition]:
        return (await self.reload(lot_id)).positions

    async def order(
        self,
        position: LotPosition,
        *,
        status: ProductionOrderStatus = ProductionOrderStatus.IN_PROGRESS,
        quantity: float | None = None,
        processed: float = 0.0,
    ) -> ProductionOrder:
        """An order on `position` whose `processed` pieces were all accepted
        in one completion row."""
        order = await self.orders.save(
            make_production_order(
                0,
                position.id,
                status=status,
                quantity=position.quantity if quantity is None else quantity,
            )
        )
        if processed:
            await self.orders.save_completion(
                ProductionOrderCompletion(
                    id=0,
                    production_order_id=order.id,
                    quantity=processed,
                    quantity_accepted=processed,
                    quantity_rejected=0.0,
                    completion_date=TODAY,
                    note=None,
                    operator_id=3,
                    recorded_by_id=3,
                    created=NOW,
                )
            )
            order.quantity_completed = processed
            if processed >= order.quantity:
                order.status = ProductionOrderStatus.COMPLETED
                order.actual_end = NOW
        return order

    async def start(self, order: ProductionOrder) -> None:
        """Gives a queued order the start that makes it IN_PROGRESS."""
        order.status = ProductionOrderStatus.IN_PROGRESS
        order.actual_start = NOW
        await self.orders.save(order)

    async def orders_of(self, position: LotPosition) -> list[ProductionOrder]:
        return await self.orders.get_by_lot_position_id(position.id)

    async def settle(self, lot_id: int) -> None:
        """Lets the reconciler store what the seeded facts derive."""
        reconciler, _ = self.request()
        reconciler.touch_lots([lot_id])
        await reconciler.run(self.planner, NOW)

    def completion_use_case(self) -> RecordProductionOrderCompletion:
        reconciler, create_lot = self.request()
        return RecordProductionOrderCompletion(
            self.orders,
            self.lots,
            None,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=reconciler,
            made_item_demand_repo=self.made_demands,
            made_item_allocation_repo=self.made_allocations,
            create_lot=create_lot,
            order_item_repo=self.order_items,
            parent_order_repo=self.parent_orders,
            interruption_repo=self.interruptions,
            source_item_demand_repo=self.source_demands,
            source_item_allocation_repo=self.source_allocations,
            bought_allocation_repo=self.bought_allocations,
            settings_repo=TenantSettings(),
        )

    def scrap_use_case(self) -> ScrapProductionPieces:
        reconciler, create_lot = self.request()
        return ScrapProductionPieces(
            self.orders,
            self.lots,
            event_bus=self.bus,
            uow=self.uow,
            made_item_demand_repo=self.made_demands,
            made_item_allocation_repo=self.made_allocations,
            create_lot=create_lot,
            reconciler=reconciler,
            interruption_repo=self.interruptions,
            order_item_repo=self.order_items,
            parent_order_repo=self.parent_orders,
            source_item_demand_repo=self.source_demands,
            source_item_allocation_repo=self.source_allocations,
            bought_allocation_repo=self.bought_allocations,
            settings_repo=TenantSettings(),
        )

    async def complete(
        self,
        order_id: int,
        quantity: float,
        *,
        rejected: float = 0.0,
        scrap: float = 0.0,
        rework: float = 0.0,
    ) -> None:
        await self.completion_use_case().execute(
            self.operator,
            order_id,
            RecordProductionOrderCompletionCommand(
                quantity=quantity,
                quantity_accepted=quantity - rejected,
                quantity_rejected=rejected,
                quantity_rework=rework,
                quantity_scrap=scrap,
                completion_date=TODAY,
            ),
        )

    async def scrap(self, order_id: int, quantity: float, *, replace: bool = False) -> list[int]:
        """Scraps pieces of the order, with a replacement lot when `replace`;
        returns the ids of the lots it created."""
        result = await self.scrap_use_case().execute(
            self.operator,
            ScrapProductionPiecesCommand(
                production_order_id=order_id,
                quantity=quantity,
                reason="tool_breakage",
                create_replacement=replace,
            ),
        )
        return [created.id for created in result.created_lots]
