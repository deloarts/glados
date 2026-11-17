"""
Unit tests for TestInspectionDisposition. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.catalogue.domain.value_objects.step_role import StepRole
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
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.errors import ProductionOrderCompletionSplitInvalidError
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
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
from tests.unit.production_lot.fakes import completion_collaborators
from tests.unit.production_lot.fakes import lot_reconciler


class FakeProductionOrderRepositoryForCompletion:
    """Richer than the minimal FakeProductionOrderRepository above (which
    only supports the delivery-propagation call shape). RecordProductionOrderCompletion
    also needs get_by_id and completion storage. An order's completions are
    kept on it, where the lifecycle reconciler reads them."""

    def __init__(self, orders: list[ProductionOrder] | None = None) -> None:
        self._orders: dict[int, ProductionOrder] = {}
        self._completions: dict[int, list[ProductionOrderCompletion]] = {}
        self._next_completion_id = 1
        # Orders the lots queue themselves take ids above the seeded ones.
        self._next_id = 100
        for order in orders or []:
            self.add(order)

    def add(self, order: ProductionOrder) -> "FakeProductionOrderRepositoryForCompletion":
        """Seeds an order, its completions with it."""
        self._orders[order.id] = order
        if order.completions:
            self._completions[order.id] = list(order.completions)
        return self

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

    async def get_by_machine_id(self, machine_id: int) -> list[ProductionOrder]:
        return [o for o in self._orders.values() if o.machine_id == machine_id]

    async def save(self, order: ProductionOrder) -> ProductionOrder:
        if order.id == 0:
            order.id = self._next_id
            self._next_id += 1
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

    async def next_production_order_number(self, template: str) -> str:
        return "PO-TEST-0001"

    async def lock_queue_scope(
        self, machine_id: int | None, machine_pool_id: int | None = None
    ) -> None:
        return None

    async def next_queue_sequence(
        self, machine_id: int | None, machine_pool_id: int | None = None
    ) -> int:
        return 1


class TestInspectionDisposition:
    """RecordProductionOrderCompletion's disposition flow:
    close-short, spawn rework/replacement lot(s), re-allocate demand
    coverage, lot lineage. Builds a real lot via a real CreateLot
    (require_qa=True auto-appends a trailing visual QA position) and
    drives completions through a real RecordProductionOrderCompletion;
    the fakes auto-increment ids and hydrate positions/steps, so this
    exercises the same orchestration a real repo would, just without a
    database."""

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
        # One order repository for the test; one reconciler per request,
        # shared by the completion and the CreateLot its disposition spawns
        # lots through (_new_request).
        self.order_repo = FakeProductionOrderRepositoryForCompletion()
        self.inspection_method_repo = FakeInspectionMethodRepository()
        self.machine_repo = FakeProductionMachineRepository()
        self._new_request()

    def _new_request(self) -> None:
        """A fresh reconciler, whose lock plan holds nothing yet, as a new
        request has, and the CreateLot that shares it."""
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
        self,
        order_repo: FakeProductionOrderRepositoryForCompletion,
        file_repo=None,
    ) -> RecordProductionOrderCompletion:
        self._new_request()
        return RecordProductionOrderCompletion(
            order_repo,
            self.lot_repo,
            file_repo,
            event_bus=self.bus,
            uow=self.uow,
            made_item_demand_repo=self.demand_repo,
            made_item_allocation_repo=self.allocation_repo,
            create_lot=self.create_lot,
            reconciler=self.reconciler,
            **completion_collaborators(order_repo),
        )

    async def _create_lot_with_demand(
        self, quantity: float, demand_id: int = 1, demand_quantity: float | None = None
    ) -> ProductionLot:
        demand_quantity = quantity if demand_quantity is None else demand_quantity
        self._new_request()
        await self.demand_repo.save(
            make_demand(id=demand_id, quantity=demand_quantity, status=MadeItemDemandStatus.OPEN)
        )
        result = await self.create_lot.execute(
            self.actor,
            CreateLotCommand(
                made_item_id=1,
                project_id=1,
                quantity=quantity,
                demand_allocations=[
                    LotDemandAllocationInput(demand_item_id=demand_id, quantity=demand_quantity)
                ],
            ),
        )
        lot = await self.lot_repo.get_by_id(result.id)
        assert lot is not None
        return lot

    async def _create_lot_no_demand(self, quantity: float) -> ProductionLot:
        self._new_request()
        result = await self.create_lot.execute(
            self.actor,
            CreateLotCommand(made_item_id=1, project_id=1, quantity=quantity),
        )
        lot = await self.lot_repo.get_by_id(result.id)
        assert lot is not None
        return lot

    async def _complete_fabrication(
        self, lot: ProductionLot, quantity: float, order_id: int = 1
    ) -> None:
        fabrication_position = lot.positions[0]
        order_repo = self.order_repo.add(
            make_production_order(
                order_id, fabrication_position.id, machine_id=1, quantity=quantity
            )
        )
        use_case = self._completion_use_case(order_repo)
        await use_case.execute(
            self.fabricator,
            production_order_id=order_id,
            cmd=RecordProductionOrderCompletionCommand(
                quantity=quantity, completion_date=date(2026, 1, 2)
            ),
        )

    async def _complete_inspection(
        self,
        lot: ProductionLot,
        qa_position_index: int,
        *,
        quantity: float,
        accepted: float,
        rejected: float,
        rework: float = 0.0,
        scrap: float = 0.0,
        order_id: int = 2,
    ):
        fresh_lot = await self.lot_repo.get_by_id(lot.id)
        qa_position = fresh_lot.positions[qa_position_index]
        order_repo = self.order_repo.add(
            make_production_order(order_id, qa_position.id, machine_id=None, quantity=quantity)
        )
        use_case = self._completion_use_case(order_repo)
        return await use_case.execute(
            self.inspector,
            production_order_id=order_id,
            cmd=RecordProductionOrderCompletionCommand(
                quantity=quantity,
                quantity_accepted=accepted,
                quantity_rejected=rejected,
                quantity_rework=rework,
                quantity_scrap=scrap,
                completion_date=date(2026, 1, 3),
            ),
        )

    async def test_trailing_qa_rejects_split_into_rework_and_scrap(self):
        lot = await self._create_lot_with_demand(quantity=6.0)
        assert len(lot.positions) == 2  # fabrication + auto-appended trailing QA
        await self._complete_fabrication(lot, 6.0)

        result = await self._complete_inspection(
            lot, 1, quantity=6.0, accepted=4.0, rejected=2.0, rework=1.0, scrap=1.0
        )

        origin = await self.lot_repo.get_by_id(lot.id)
        assert origin.quantity == 4.0
        assert origin.status == "completed"

        assert len(result.created_lots) == 2
        rework_summary = next(c for c in result.created_lots if c.disposition == "rework")
        replacement_summary = next(c for c in result.created_lots if c.disposition == "replacement")

        rework_lot = await self.lot_repo.get_by_id(rework_summary.id)
        assert rework_lot.quantity == 1.0
        assert rework_lot.made_item_id == origin.made_item_id
        assert rework_lot.project_id == origin.project_id
        assert rework_lot.origin_lot_id == origin.id
        assert rework_lot.origin_disposition == "rework"
        assert rework_lot.source_made_item_id == origin.made_item_id  # self-alteration

        replacement_lot = await self.lot_repo.get_by_id(replacement_summary.id)
        assert replacement_lot.quantity == 1.0
        assert replacement_lot.origin_lot_id == origin.id
        assert replacement_lot.origin_disposition == "replacement"
        assert replacement_lot.source_made_item_id is None

        # Born internal applies to disposition-spawned lots too:
        # require_qa is still on, so both follow-up lots get their own
        # trailing QA position, auto-queued in the same commit as the
        # completion that spawned them, not left stranded unassigned.
        for follow_up in (rework_lot, replacement_lot):
            qa_position = follow_up.positions[-1]
            assert qa_position.steps[0].role == "inspection"
            assert qa_position.kind == "internal"
            assert len(qa_position.production_orders) == 1
            assert qa_position.production_orders[0].machine_id is None
            assert qa_position.production_orders[0].status == "queued"

        # Allocations: original 6 -> 4, rework gets 1, replacement gets 1.
        original_allocations = await self.allocation_repo.get_by_lot_id(origin.id)
        assert len(original_allocations) == 1
        assert original_allocations[0].quantity == 4.0
        assert (await self.allocation_repo.get_by_lot_id(rework_lot.id))[0].quantity == 1.0
        assert (await self.allocation_repo.get_by_lot_id(replacement_lot.id))[0].quantity == 1.0

        # Demand status recomputed: 4+1+1=6 still fully covers the demand,
        # and it's "ordered" (not just "allocated") since the completed
        # origin lot alone is already beyond DRAFT (promote_to_ordered).
        assert (await self.demand_repo.get_by_id(1)).status == "ordered"

        events = await self.lot_repo.get_events(origin.id)
        assert any(e.event_type == LotEventType.LOT_CLOSED_SHORT for e in events)
        assert any(e.event_type == LotEventType.REWORK_LOT_CREATED for e in events)
        assert any(e.event_type == LotEventType.REPLACEMENT_LOT_CREATED for e in events)

    async def test_mid_routing_inspection_shrinks_downstream_and_lot_continues(self):
        # A second fabrication process after the inspection: require_qa
        # doesn't apply here (routing already isn't trailing-QA shaped),
        # but the catalogue can still place an inspection process
        # mid-routing directly.
        self.made_item_repo = FakeMadeItemRepository(
            [
                make_made_item(
                    processes=[
                        make_process(id=1, position=0, fabrication_method_id=1, group_index=0),
                        make_process(
                            id=2,
                            position=1,
                            fabrication_method_id=None,
                            group_index=1,
                            role=StepRole.INSPECTION,
                            inspection_method_id=1,
                        ),
                        make_process(id=3, position=2, fabrication_method_id=1, group_index=2),
                    ]
                )
            ]
        )
        self.settings_repo = FakeAdminSettingsRepository(require_qa=False)
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

        lot = await self._create_lot_no_demand(quantity=6.0)
        assert len(lot.positions) == 3
        await self._complete_fabrication(lot, 6.0, order_id=1)

        await self._complete_inspection(
            lot, 1, quantity=6.0, accepted=4.0, rejected=2.0, rework=2.0, scrap=0.0, order_id=2
        )

        origin = await self.lot_repo.get_by_id(lot.id)
        assert origin.quantity == 4.0
        # The final (3rd) position hasn't produced anything yet, so the lot
        # is not done, it continues at the new, smaller quantity.
        assert origin.status != "completed"
        downstream_position = origin.positions[2]
        assert downstream_position.quantity == 4.0
        # The already-fully-executed first (fabrication) position is
        # history and keeps its original quantity.
        assert origin.positions[0].quantity == 6.0

    async def test_multiple_partial_batches_with_rejects(self):
        lot = await self._create_lot_with_demand(quantity=10.0)
        await self._complete_fabrication(lot, 10.0)

        qa_position = (await self.lot_repo.get_by_id(lot.id)).positions[1]
        order_repo = self.order_repo.add(
            make_production_order(2, qa_position.id, machine_id=None, quantity=10.0)
        )
        use_case = self._completion_use_case(order_repo)

        # Batch 1: 4 processed (3 accepted, 1 rejected -> reworked).
        await use_case.execute(
            self.inspector,
            production_order_id=2,
            cmd=RecordProductionOrderCompletionCommand(
                quantity=4.0,
                quantity_accepted=3.0,
                quantity_rejected=1.0,
                quantity_rework=1.0,
                quantity_scrap=0.0,
                completion_date=date(2026, 1, 3),
            ),
        )
        assert (await self.lot_repo.get_by_id(lot.id)).quantity == 9.0

        # Batch 2 on the SAME order: 6 more processed (5 accepted, 1
        # rejected -> scrapped), bringing the order's processed total to
        # 4 + 6 = 10 = order.quantity (completes it).
        await use_case.execute(
            self.inspector,
            production_order_id=2,
            cmd=RecordProductionOrderCompletionCommand(
                quantity=6.0,
                quantity_accepted=5.0,
                quantity_rejected=1.0,
                quantity_rework=0.0,
                quantity_scrap=1.0,
                completion_date=date(2026, 1, 4),
            ),
        )

        final_origin = await self.lot_repo.get_by_id(lot.id)
        # Two disposition batches: 10 - 1 - 1 = 8.
        assert final_origin.quantity == 8.0
        assert final_origin.status == "completed"
        # Each batch spawned its own rework/replacement lot: 2 rework-
        # capable + 2 replacement-capable events total across both calls.
        events = await self.lot_repo.get_events(final_origin.id)
        assert len([e for e in events if e.event_type == LotEventType.LOT_CLOSED_SHORT]) == 2
        assert len([e for e in events if e.event_type == LotEventType.REWORK_LOT_CREATED]) == 1
        assert len([e for e in events if e.event_type == LotEventType.REPLACEMENT_LOT_CREATED]) == 1

    async def test_the_rejected_piece_is_cut_from_the_newest_demand(self):
        await self.demand_repo.save(
            make_demand(id=1, quantity=2.0, status=MadeItemDemandStatus.OPEN)
        )
        await self.demand_repo.save(
            make_demand(id=2, quantity=4.0, status=MadeItemDemandStatus.OPEN)
        )
        result = await self.create_lot.execute(
            self.actor,
            CreateLotCommand(
                made_item_id=1,
                project_id=1,
                quantity=6.0,
                demand_allocations=[
                    LotDemandAllocationInput(demand_item_id=1, quantity=2.0),
                    LotDemandAllocationInput(demand_item_id=2, quantity=4.0),
                ],
            ),
        )
        lot = await self.lot_repo.get_by_id(result.id)
        await self._complete_fabrication(lot, 6.0)

        # The fully allocated lot of 6 closes at 5: the one rejected piece
        # is cut from the end of the fill, so demand 2, the newer one, gives
        # it up and its piece moves to the rework lot.
        result = await self._complete_inspection(
            lot, 1, quantity=6.0, accepted=5.0, rejected=1.0, rework=1.0, scrap=0.0
        )

        kept = {
            a.demand_item_id: a.quantity for a in await self.allocation_repo.get_by_lot_id(lot.id)
        }
        assert kept == {1: 2.0, 2: 3.0}
        [rework_lot] = result.created_lots
        shares = {
            a.demand_item_id: a.quantity
            for a in await self.allocation_repo.get_by_lot_id(rework_lot.id)
        }
        assert shares == {2: 1.0}

    async def test_a_partly_allocated_lot_moves_nothing_it_did_not_cut(self):
        await self.demand_repo.save(
            make_demand(id=1, quantity=1.0, status=MadeItemDemandStatus.OPEN)
        )
        await self.demand_repo.save(
            make_demand(id=2, quantity=2.0, status=MadeItemDemandStatus.OPEN)
        )
        result = await self.create_lot.execute(
            self.actor,
            CreateLotCommand(
                made_item_id=1,
                project_id=1,
                quantity=6.0,
                demand_allocations=[
                    LotDemandAllocationInput(demand_item_id=1, quantity=1.0),
                    LotDemandAllocationInput(demand_item_id=2, quantity=2.0),
                ],
            ),
        )
        lot = await self.lot_repo.get_by_id(result.id)
        await self._complete_fabrication(lot, 6.0)

        # Allocations of 3 still fit the new quantity of 5: nothing is cut,
        # so the rework lot takes no allocation either.
        result = await self._complete_inspection(
            lot, 1, quantity=6.0, accepted=5.0, rejected=1.0, rework=1.0, scrap=0.0
        )

        kept = {
            a.demand_item_id: a.quantity for a in await self.allocation_repo.get_by_lot_id(lot.id)
        }
        assert kept == {1: 1.0, 2: 2.0}
        [rework_lot] = result.created_lots
        assert await self.allocation_repo.get_by_lot_id(rework_lot.id) == []

    async def test_no_allocations_skips_reallocation_entirely(self):
        lot = await self._create_lot_no_demand(quantity=6.0)
        await self._complete_fabrication(lot, 6.0)

        result = await self._complete_inspection(
            lot, 1, quantity=6.0, accepted=4.0, rejected=2.0, rework=1.0, scrap=1.0
        )

        assert len(result.created_lots) == 2
        for created in result.created_lots:
            assert await self.allocation_repo.get_by_lot_id(created.id) == []

    async def test_rework_only_creates_a_single_follow_up_lot(self):
        lot = await self._create_lot_with_demand(quantity=6.0)
        await self._complete_fabrication(lot, 6.0)

        result = await self._complete_inspection(
            lot, 1, quantity=6.0, accepted=4.0, rejected=2.0, rework=2.0, scrap=0.0
        )

        assert len(result.created_lots) == 1
        assert result.created_lots[0].disposition == "rework"

    async def test_scrap_only_creates_a_single_follow_up_lot(self):
        lot = await self._create_lot_with_demand(quantity=6.0)
        await self._complete_fabrication(lot, 6.0)

        result = await self._complete_inspection(
            lot, 1, quantity=6.0, accepted=4.0, rejected=2.0, rework=0.0, scrap=2.0
        )

        assert len(result.created_lots) == 1
        assert result.created_lots[0].disposition == "replacement"

    async def test_disposition_sum_not_matching_rejected_raises(self):
        lot = await self._create_lot_with_demand(quantity=6.0)
        await self._complete_fabrication(lot, 6.0)

        with pytest.raises(ProductionOrderCompletionSplitInvalidError):
            await self._complete_inspection(
                lot, 1, quantity=6.0, accepted=4.0, rejected=2.0, rework=1.0, scrap=0.0
            )

    async def test_disposition_on_non_inspection_order_rejected(self):
        lot = await self._create_lot_with_demand(quantity=6.0)
        fabrication_position = lot.positions[0]
        order_repo = self.order_repo.add(
            make_production_order(1, fabrication_position.id, machine_id=1)
        )
        use_case = self._completion_use_case(order_repo)
        with pytest.raises(ProductionOrderCompletionSplitInvalidError):
            await use_case.execute(
                self.fabricator,
                production_order_id=1,
                cmd=RecordProductionOrderCompletionCommand(
                    quantity=6.0,
                    quantity_accepted=4.0,
                    quantity_rejected=2.0,
                    quantity_rework=1.0,
                    quantity_scrap=1.0,
                    completion_date=date(2026, 1, 2),
                ),
            )

    async def test_disposition_requires_write_inspections_permission(self):
        lot = await self._create_lot_with_demand(quantity=6.0)
        await self._complete_fabrication(lot, 6.0)
        fresh_lot = await self.lot_repo.get_by_id(lot.id)
        qa_position = fresh_lot.positions[1]
        order_repo = self.order_repo.add(
            make_production_order(2, qa_position.id, machine_id=None, quantity=6.0)
        )
        use_case = self._completion_use_case(order_repo)
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(
                self.fabricator,  # no write:inspections
                production_order_id=2,
                cmd=RecordProductionOrderCompletionCommand(
                    quantity=6.0,
                    quantity_accepted=4.0,
                    quantity_rejected=2.0,
                    quantity_rework=1.0,
                    quantity_scrap=1.0,
                    completion_date=date(2026, 1, 2),
                ),
            )
