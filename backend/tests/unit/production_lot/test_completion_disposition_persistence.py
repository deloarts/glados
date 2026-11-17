"""
Unit test verifying that RecordProductionOrderCompletion persists
quantity_rework/quantity_scrap onto the saved ProductionOrderCompletion
row, besides using them to drive rework/replacement lot spawning. Setup
mirrors
test_inspection_disposition.py's TestInspectionDisposition (a real lot
built via a real CreateLot with require_qa=True), duplicated rather than
imported to keep this file self-contained. No database, no HTTP.
"""

from datetime import date

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.dto.production_lot_dto import CreateLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import LotDemandAllocationInput
from src.modules.fulfillment.application.dto.production_order_dto import (
    RecordProductionOrderCompletionCommand,
)
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.application.use_cases.production_order.record_production_order_completion import (
    RecordProductionOrderCompletion,
)
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_lot._helpers import make_demand
from tests.unit.production_lot._helpers import make_made_item
from tests.unit.production_lot._helpers import make_process
from tests.unit.production_lot._helpers import make_production_order
from tests.unit.production_lot.fakes import FakeAdminSettingsRepository
from tests.unit.production_lot.fakes import FakeEventBus
from tests.unit.production_lot.fakes import FakeInspectionMethodRepository
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeMadeItemRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionMachineRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_lot.fakes import completion_collaborators
from tests.unit.production_lot.fakes import lot_reconciler
from tests.unit.production_lot.test_inspection_disposition import (
    FakeProductionOrderRepositoryForCompletion,
)


class TestCompletionDispositionPersistence:
    def setup_method(self):
        self.lot_repo = FakeProductionLotRepository()
        self.demand_repo = FakeMadeItemDemandRepository()
        self.allocation_repo = FakeMadeItemAllocationRepository()
        self.settings_repo = FakeAdminSettingsRepository(require_qa=True)
        self.source_item_demand_repo = FakeSourceItemDemandRepository()
        self.uow = FakeUnitOfWork()
        self.bus = FakeEventBus()
        self.actor = make_user(id=1, permissions=[Permission.WRITE_LOTS])
        self.inspector = make_user(
            id=2, permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.WRITE_INSPECTIONS]
        )
        self.fabricator = make_user(id=3, permissions=[Permission.WRITE_PRODUCTION_ORDERS])

        self.made_item_repo = FakeMadeItemRepository(
            [make_made_item(processes=[make_process(id=1, position=0, fabrication_method_id=1)])]
        )
        self.order_repo = FakeProductionOrderRepositoryForCompletion()
        self.inspection_method_repo = FakeInspectionMethodRepository()
        self.machine_repo = FakeProductionMachineRepository()
        self._new_request()

    def _new_request(self) -> None:
        """A fresh reconciler and CreateLot, as each request has its own in
        the app: one reconciler per request, shared by the completion and the
        CreateLot its disposition spawns lots through. The reconciler reads
        the made demand and allocation fakes."""
        self.reconciler = lot_reconciler(
            self.lot_repo,
            self.order_repo,
            bus=self.bus,
            made_demands=self.demand_repo,
            made_allocations=self.allocation_repo,
        )
        self.create_lot = CreateLot(
            lot_repo=self.lot_repo,
            made_item_repo=self.made_item_repo,
            demand_repo=self.demand_repo,
            allocation_repo=self.allocation_repo,
            settings_repo=self.settings_repo,
            source_item_demand_repo=self.source_item_demand_repo,
            order_repo=self.order_repo,
            inspection_method_repo=self.inspection_method_repo,
            machine_repo=self.machine_repo,
            uow=self.uow,
            event_bus=FakeEventBus(),
            reconciler=self.reconciler,
        )

    def _completion_use_case(
        self, order_repo: FakeProductionOrderRepositoryForCompletion
    ) -> RecordProductionOrderCompletion:
        self._new_request()
        return RecordProductionOrderCompletion(
            order_repo,
            self.lot_repo,
            None,
            event_bus=self.bus,
            uow=self.uow,
            made_item_demand_repo=self.demand_repo,
            made_item_allocation_repo=self.allocation_repo,
            create_lot=self.create_lot,
            reconciler=self.reconciler,
            **completion_collaborators(order_repo),
        )

    async def _create_lot_with_demand(self, quantity: float) -> ProductionLot:
        await self.demand_repo.save(
            make_demand(id=1, quantity=quantity, status=MadeItemDemandStatus.OPEN)
        )
        result = await self.create_lot.execute(
            self.actor,
            CreateLotCommand(
                made_item_id=1,
                project_id=1,
                quantity=quantity,
                demand_allocations=[LotDemandAllocationInput(demand_item_id=1, quantity=quantity)],
            ),
        )
        lot = await self.lot_repo.get_by_id(result.id)
        assert lot is not None
        return lot

    async def _complete_fabrication(self, lot: ProductionLot, quantity: float) -> None:
        fabrication_position = lot.positions[0]
        order_repo = self.order_repo.add(
            make_production_order(1, fabrication_position.id, machine_id=1, quantity=quantity)
        )
        await self._completion_use_case(order_repo).execute(
            self.fabricator,
            production_order_id=1,
            cmd=RecordProductionOrderCompletionCommand(
                quantity=quantity, completion_date=date(2026, 1, 2)
            ),
        )

    async def test_completion_persists_rework_and_scrap_on_the_completion_row(self):
        lot = await self._create_lot_with_demand(quantity=6.0)
        await self._complete_fabrication(lot, 6.0)

        fresh_lot = await self.lot_repo.get_by_id(lot.id)
        qa_position = fresh_lot.positions[1]
        order_repo = self.order_repo.add(
            make_production_order(2, qa_position.id, machine_id=None, quantity=6.0)
        )
        await self._completion_use_case(order_repo).execute(
            self.inspector,
            production_order_id=2,
            cmd=RecordProductionOrderCompletionCommand(
                quantity=6.0,
                quantity_accepted=4.0,
                quantity_rejected=2.0,
                quantity_rework=1.0,
                quantity_scrap=1.0,
                completion_date=date(2026, 1, 3),
            ),
        )

        stored = (await order_repo.get_completions(2))[-1]
        assert stored.quantity_rework == 1.0
        assert stored.quantity_scrap == 1.0
        assert stored.quantity_rejected == 2.0

    async def test_ordinary_completion_persists_zero_rework_and_scrap(self):
        lot = await self._create_lot_with_demand(quantity=6.0)
        fabrication_position = lot.positions[0]
        order_repo = self.order_repo.add(
            make_production_order(1, fabrication_position.id, machine_id=1, quantity=6.0)
        )
        await self._completion_use_case(order_repo).execute(
            self.fabricator,
            production_order_id=1,
            cmd=RecordProductionOrderCompletionCommand(
                quantity=6.0, completion_date=date(2026, 1, 2)
            ),
        )

        stored = (await order_repo.get_completions(1))[-1]
        assert stored.quantity_rework == 0.0
        assert stored.quantity_scrap == 0.0
