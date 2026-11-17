"""
Unit tests for ScrapProductionPieces/ScrapLotPieces: the position-capacity
cap, the terminal `scrapped` transition, quantity_scrapped accumulation,
the replacement opt-out, and replacement-lot inheritance of the origin's
routing/date/priority/demand allocation. Builds a real lot via a real
CreateLot and drives scrap calls
through a real ScrapProductionPieces/ScrapLotPieces, the same style
test_inspection_disposition.py uses for the QA/inspection path, so the
two disposition paths are exercised the same way.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.dto.production_lot_dto import CreateLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import LotDemandAllocationInput
from src.modules.fulfillment.application.dto.production_lot_dto import ScrapLotPiecesCommand
from src.modules.fulfillment.application.dto.production_order_dto import (
    ScrapProductionPiecesCommand,
)
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.application.use_cases.production_order.scrap_lot_pieces import (
    ScrapLotPieces,
)
from src.modules.fulfillment.application.use_cases.production_order.scrap_production_pieces import (
    ScrapProductionPieces,
)
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.errors import ProductionOrderInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import ProductionOrderSelectionRequiredError
from src.modules.fulfillment.domain.errors import ScrapQuantityExceedsAvailableError
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
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
from tests.unit.production_lot.fakes import disposition_collaborators
from tests.unit.production_lot.fakes import lot_reconciler
from tests.unit.production_order.fakes import FakeProductionOrderInterruptionRepository


class FakeProductionOrderRepositoryForScrap:
    """Same shape as test_inspection_disposition.py's own completion-
    capable fake: ScrapProductionPieces needs get_by_id, get_completions
    and completion storage on top of the minimal FakeProductionOrderRepository.
    An order's completions are kept on it, where the lifecycle reconciler
    reads them."""

    def __init__(self, orders: list[ProductionOrder] | None = None) -> None:
        self._orders: dict[int, ProductionOrder] = {o.id: o for o in (orders or [])}
        self._completions: dict[int, list[ProductionOrderCompletion]] = {
            o.id: list(o.completions) for o in (orders or []) if o.completions
        }
        self._next_completion_id = 1

    async def get_by_id(self, id: int) -> ProductionOrder | None:
        return self._orders.get(id)

    async def get_by_id_for_update(self, id: int) -> ProductionOrder | None:
        return self._orders.get(id)

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[ProductionOrder]:
        return [self._orders[i] for i in ids if i in self._orders]

    async def lock_for_update(self, ids: list[int]) -> None:
        return None

    async def get_by_lot_position_id(self, lot_position_id: int) -> list[ProductionOrder]:
        return [o for o in self._orders.values() if o.lot_position_id == lot_position_id]

    async def get_by_lot_position_ids(
        self, lot_position_ids: list[int], *, refresh: bool = False
    ) -> list[ProductionOrder]:
        return [o for o in self._orders.values() if o.lot_position_id in lot_position_ids]

    def add(self, order: ProductionOrder) -> None:
        """Seeds an order, its completions with it."""
        self._orders[order.id] = order
        if order.completions:
            self._completions[order.id] = list(order.completions)

    async def save(self, order: ProductionOrder) -> ProductionOrder:
        self._orders[order.id] = order
        return order

    async def get_completions(self, production_order_id: int) -> list[ProductionOrderCompletion]:
        return self._completions.get(production_order_id, [])

    async def save_completion(
        self, completion: ProductionOrderCompletion
    ) -> ProductionOrderCompletion:
        if completion.id == 0:
            completion.id = self._next_completion_id
            self._next_completion_id += 1
        self._completions.setdefault(completion.production_order_id, []).append(completion)
        if completion.production_order_id in self._orders:
            self._orders[completion.production_order_id].completions = self._completions[
                completion.production_order_id
            ]
        return completion


class TestScrapProductionPieces:
    def setup_method(self):
        self.lot_repo = FakeProductionLotRepository()
        self.demand_repo = FakeMadeItemDemandRepository()
        self.allocation_repo = FakeMadeItemAllocationRepository()
        self.settings_repo = FakeAdminSettingsRepository(require_qa=False)
        self.source_item_demand_repo = FakeSourceItemDemandRepository()
        self.uow = FakeUnitOfWork()
        self.bus = FakeEventBus()
        self.actor = make_user(id=1, permissions=[Permission.WRITE_LOTS])
        self.operator = make_user(id=3, permissions=[Permission.WRITE_PRODUCTION_ORDERS])

        self.made_item_repo = FakeMadeItemRepository(
            [make_made_item(processes=[make_process(id=1, position=0, fabrication_method_id=1)])]
        )
        self.order_repo = FakeProductionOrderRepositoryForScrap()
        self.inspection_method_repo = FakeInspectionMethodRepository()
        self.machine_repo = FakeProductionMachineRepository()
        self._new_request()

    def _new_request(self) -> None:
        """A fresh reconciler and CreateLot, as each request has its own in
        the app: one reconciler per request, shared by the scrap and the
        CreateLot its disposition spawns follow-up lots through. The
        reconciler reads the made demand and allocation fakes, so the lot's
        demands show the statuses their derivation gives."""
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

    def _scrap_use_case(
        self, order_repo: FakeProductionOrderRepositoryForScrap
    ) -> ScrapProductionPieces:
        return ScrapProductionPieces(
            order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            made_item_demand_repo=self.demand_repo,
            made_item_allocation_repo=self.allocation_repo,
            create_lot=self.create_lot,
            reconciler=self.reconciler,
            interruption_repo=FakeProductionOrderInterruptionRepository(order_repo._orders),
            **disposition_collaborators(),
        )

    async def _create_lot_with_demand(
        self,
        quantity: float,
        demand_id: int = 1,
        demand_quantity: float | None = None,
        required_delivery_date: date | None = None,
        priority: str | None = None,
    ) -> ProductionLot:
        demand_quantity = quantity if demand_quantity is None else demand_quantity
        await self.demand_repo.save(
            make_demand(id=demand_id, quantity=demand_quantity, status=MadeItemDemandStatus.OPEN)
        )
        result = await self.create_lot.execute(
            self.actor,
            CreateLotCommand(
                made_item_id=1,
                project_id=1,
                quantity=quantity,
                required_delivery_date=required_delivery_date,
                priority=priority,
                demand_allocations=[
                    LotDemandAllocationInput(demand_item_id=demand_id, quantity=demand_quantity)
                ],
            ),
        )
        lot = await self.lot_repo.get_by_id(result.id)
        assert lot is not None
        self._new_request()
        return lot

    async def _queue_order(
        self, lot: ProductionLot, order_id: int, quantity: float
    ) -> FakeProductionOrderRepositoryForScrap:
        fabrication_position = (await self.lot_repo.get_by_id(lot.id)).positions[0]
        self.order_repo.add(
            make_production_order(
                order_id, fabrication_position.id, machine_id=1, quantity=quantity
            )
        )
        return self.order_repo

    async def test_scrap_full_quantity_sets_lot_scrapped_and_replacement_inherits_schedule(self):
        due = date(2026, 3, 1)
        lot = await self._create_lot_with_demand(
            quantity=4.0, required_delivery_date=due, priority="high"
        )
        order_repo = await self._queue_order(lot, order_id=1, quantity=4.0)
        use_case = self._scrap_use_case(order_repo)

        result = await use_case.execute(
            self.operator,
            ScrapProductionPiecesCommand(
                production_order_id=1,
                quantity=4.0,
                reason="tool_breakage",
                create_replacement=True,
            ),
        )

        origin = await self.lot_repo.get_by_id(lot.id)
        assert origin.quantity == 0.0
        assert origin.status == "scrapped"
        assert origin.quantity_scrapped == 4.0
        assert result.lot.status == "scrapped"

        assert len(result.created_lots) == 1
        assert result.created_lots[0].disposition == "replacement"
        replacement = await self.lot_repo.get_by_id(result.created_lots[0].id)
        assert replacement.quantity == 4.0
        assert replacement.made_item_id == origin.made_item_id
        assert replacement.project_id == origin.project_id
        assert replacement.origin_lot_id == origin.id
        assert replacement.origin_disposition == "replacement"
        # Inherits required_delivery_date and priority from the origin.
        assert replacement.required_delivery_date == due
        assert replacement.priority == "high"
        # Routing: the replacement is a full snapshot of the made item's
        # own routing, same as any freshly-created lot.
        assert len(replacement.positions) == 1

        # Allocation fully moved onto the replacement lot.
        assert await self.allocation_repo.get_by_lot_id(origin.id) == [] or all(
            a.quantity == 0 for a in await self.allocation_repo.get_by_lot_id(origin.id)
        )
        assert (await self.allocation_repo.get_by_lot_id(replacement.id))[0].quantity == 4.0

        events = await self.lot_repo.get_events(origin.id)
        assert any(e.event_type == LotEventType.PIECES_SCRAPPED for e in events)
        assert any(e.event_type == LotEventType.REPLACEMENT_LOT_CREATED for e in events)

        published_types = [type(e).__name__ for e in self.bus.published]
        assert "PiecesScrapped" in published_types
        assert "LotCreated" in published_types

    async def test_scrap_partial_quantity_leaves_lot_in_progress_and_accumulates(self):
        lot = await self._create_lot_with_demand(quantity=10.0)
        # Its raw material has arrived, so the running first position keeps
        # input to scrap from once it derives internal.
        lot.input_demand_id = 77
        self.lot_repo._raw_material_arrived_by_demand[77] = 10.0
        await self.lot_repo.save(lot)
        order_repo = await self._queue_order(lot, order_id=1, quantity=10.0)
        use_case = self._scrap_use_case(order_repo)

        await use_case.execute(
            self.operator,
            ScrapProductionPiecesCommand(
                production_order_id=1,
                quantity=2.0,
                reason="operator_error",
                create_replacement=False,
            ),
        )
        after_first = await self.lot_repo.get_by_id(lot.id)
        assert after_first.quantity == 8.0
        assert after_first.quantity_scrapped == 2.0
        assert after_first.status != "scrapped"

        await use_case.execute(
            self.operator,
            ScrapProductionPiecesCommand(
                production_order_id=1,
                quantity=3.0,
                reason="operator_error",
                create_replacement=False,
            ),
        )
        after_second = await self.lot_repo.get_by_id(lot.id)
        assert after_second.quantity == 5.0
        assert after_second.quantity_scrapped == 5.0
        assert after_second.status != "scrapped"

    async def test_scrap_opt_out_reduces_allocation_without_replacement_lot(self):
        lot = await self._create_lot_with_demand(quantity=4.0)
        order_repo = await self._queue_order(lot, order_id=1, quantity=4.0)
        use_case = self._scrap_use_case(order_repo)

        result = await use_case.execute(
            self.operator,
            ScrapProductionPiecesCommand(
                production_order_id=1,
                quantity=4.0,
                reason="material_defect",
                create_replacement=False,
            ),
        )

        assert result.created_lots == []
        origin = await self.lot_repo.get_by_id(lot.id)
        assert origin.status == "scrapped"
        remaining = await self.allocation_repo.get_by_lot_id(origin.id)
        assert remaining == [] or all(a.quantity == 0 for a in remaining)

        events = await self.lot_repo.get_events(origin.id)
        assert any(e.event_type == LotEventType.REPLACEMENT_SKIPPED for e in events)
        assert not any(e.event_type == LotEventType.REPLACEMENT_LOT_CREATED for e in events)

    async def test_scrap_over_capacity_raises(self):
        lot = await self._create_lot_no_demand(quantity=4.0)
        order_repo = await self._queue_order(lot, order_id=1, quantity=4.0)
        use_case = self._scrap_use_case(order_repo)

        with pytest.raises(ScrapQuantityExceedsAvailableError):
            await use_case.execute(
                self.operator,
                ScrapProductionPiecesCommand(production_order_id=1, quantity=5.0, reason="other"),
            )

    async def test_scrap_requires_write_production_orders_permission(self):
        lot = await self._create_lot_no_demand(quantity=4.0)
        order_repo = await self._queue_order(lot, order_id=1, quantity=4.0)
        use_case = self._scrap_use_case(order_repo)
        unauthorized = make_user(id=9, permissions=[])

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(
                unauthorized,
                ScrapProductionPiecesCommand(production_order_id=1, quantity=1.0, reason="other"),
            )

    async def test_scrap_on_non_in_progress_order_rejected(self):
        lot = await self._create_lot_no_demand(quantity=4.0)
        fabrication_position = (await self.lot_repo.get_by_id(lot.id)).positions[0]
        order_repo = self.order_repo
        order_repo.add(
            make_production_order(
                1,
                fabrication_position.id,
                status=ProductionOrderStatus.QUEUED,
                quantity=4.0,
            )
        )
        use_case = self._scrap_use_case(order_repo)

        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await use_case.execute(
                self.operator,
                ScrapProductionPiecesCommand(production_order_id=1, quantity=1.0, reason="other"),
            )

    async def _create_lot_no_demand(self, quantity: float) -> ProductionLot:
        result = await self.create_lot.execute(
            self.actor,
            CreateLotCommand(made_item_id=1, project_id=1, quantity=quantity),
        )
        lot = await self.lot_repo.get_by_id(result.id)
        assert lot is not None
        self._new_request()
        return lot


class TestScrapLotPieces:
    def setup_method(self):
        self.lot_repo = FakeProductionLotRepository()
        self.demand_repo = FakeMadeItemDemandRepository()
        self.allocation_repo = FakeMadeItemAllocationRepository()
        self.settings_repo = FakeAdminSettingsRepository(require_qa=False)
        self.source_item_demand_repo = FakeSourceItemDemandRepository()
        self.uow = FakeUnitOfWork()
        self.bus = FakeEventBus()
        self.actor = make_user(
            id=1, permissions=[Permission.WRITE_LOTS, Permission.WRITE_PRODUCTION_ORDERS]
        )

        self.made_item_repo = FakeMadeItemRepository(
            [make_made_item(processes=[make_process(id=1, position=0, fabrication_method_id=1)])]
        )
        self.order_repo = FakeProductionOrderRepositoryForScrap()
        # One reconciler per request, shared by the scrap and the CreateLot
        # its disposition spawns follow-up lots through.
        self.reconciler = lot_reconciler(self.lot_repo, self.order_repo, bus=self.bus)
        self.inspection_method_repo = FakeInspectionMethodRepository()
        self.machine_repo = FakeProductionMachineRepository()
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

    async def _create_lot(self, quantity: float) -> ProductionLot:
        result = await self.create_lot.execute(
            self.actor,
            CreateLotCommand(made_item_id=1, project_id=1, quantity=quantity),
        )
        lot = await self.lot_repo.get_by_id(result.id)
        assert lot is not None
        return lot

    async def test_resolves_single_open_order_when_id_omitted(self):
        lot = await self._create_lot(quantity=4.0)
        position = (await self.lot_repo.get_by_id(lot.id)).positions[0]
        order_repo = self.order_repo
        order_repo.add(make_production_order(1, position.id, machine_id=1, quantity=4.0))
        scrap_production_pieces = ScrapProductionPieces(
            order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            made_item_demand_repo=self.demand_repo,
            made_item_allocation_repo=self.allocation_repo,
            create_lot=self.create_lot,
            reconciler=self.reconciler,
            interruption_repo=FakeProductionOrderInterruptionRepository(order_repo._orders),
            **disposition_collaborators(),
        )
        use_case = ScrapLotPieces(self.lot_repo, order_repo, scrap_production_pieces)

        result = await use_case.execute(
            self.actor,
            lot.id,
            ScrapLotPiecesCommand(position_id=position.id, quantity=1.0, reason="tool_breakage"),
        )
        assert result.lot.quantity_scrapped == 1.0

    async def test_ambiguous_open_orders_require_explicit_id(self):
        lot = await self._create_lot(quantity=4.0)
        position = (await self.lot_repo.get_by_id(lot.id)).positions[0]
        order_repo = self.order_repo
        order_repo.add(make_production_order(1, position.id, machine_id=1, quantity=2.0))
        order_repo.add(make_production_order(2, position.id, machine_id=2, quantity=2.0))
        scrap_production_pieces = ScrapProductionPieces(
            order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            made_item_demand_repo=self.demand_repo,
            made_item_allocation_repo=self.allocation_repo,
            create_lot=self.create_lot,
            reconciler=self.reconciler,
            interruption_repo=FakeProductionOrderInterruptionRepository(order_repo._orders),
            **disposition_collaborators(),
        )
        use_case = ScrapLotPieces(self.lot_repo, order_repo, scrap_production_pieces)

        with pytest.raises(ProductionOrderSelectionRequiredError):
            await use_case.execute(
                self.actor,
                lot.id,
                ScrapLotPiecesCommand(
                    position_id=position.id, quantity=1.0, reason="tool_breakage"
                ),
            )
