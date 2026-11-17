"""
Covers recording a production order's completion: quantity bookkeeping, permission gating
between ordinary and inspection positions, and the lot/position status effects a completion
triggers. Unit tests for TestRecordProductionOrderCompletion. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.production_order_dto import (
    RecordProductionOrderCompletionCommand,
)
from src.modules.fulfillment.application.use_cases.production_order.record_production_order_completion import (
    RecordProductionOrderCompletion,
)
from src.modules.fulfillment.domain.entities.production_order_file import ProductionOrderFile
from src.modules.fulfillment.domain.errors import LotPositionOverflowError
from src.modules.fulfillment.domain.errors import OperatorSelectionRequiredError
from src.modules.fulfillment.domain.errors import ProductionOrderCompletionSplitInvalidError
from src.modules.fulfillment.domain.errors import ProductionOrderInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import ProductionOrderMeasurementEvidenceRequiredError
from src.modules.fulfillment.domain.errors import ProductionOrderQuantityOverflowError
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCompleted
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_order_file_category import (
    ProductionOrderFileCategory,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_lot._helpers import NoLotCreation
from tests.unit.production_lot._helpers import RecordingLotCreation
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import completion_collaborators
from tests.unit.production_order._helpers import make_lot
from tests.unit.production_order._helpers import make_order
from tests.unit.production_order._helpers import make_position
from tests.unit.production_order._helpers import make_step
from tests.unit.production_order.fakes import FakeEventBus
from tests.unit.production_order.fakes import FakeProductionLotRepository
from tests.unit.production_order.fakes import FakeProductionOrderFileRepository
from tests.unit.production_order.fakes import FakeProductionOrderRepository
from tests.unit.production_order.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import production_order_reconciler

_INSPECTOR = make_user(
    id=2, permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.WRITE_INSPECTIONS]
)


class TestRecordProductionOrderCompletion:
    def setup_method(self):
        self.position = make_position(id=1, quantity=10.0, kind=LotPositionKind.INTERNAL)
        self.lot = make_lot(positions=[self.position])
        # Rework lot by default, exempt from sequence-1 raw-material gating,
        # since most of these tests exercise order/position-level completion
        # caps, not raw material. The raw_material_* tests below override
        # this back to a bought/source-sourced lot to test that gating.
        self.lot.source_made_item_id = 99
        self.lot_repo = FakeProductionLotRepository([self.lot])
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])

    def _use_case(
        self,
        order_repo: FakeProductionOrderRepository,
        file_repo: FakeProductionOrderFileRepository | None = None,
    ) -> RecordProductionOrderCompletion:
        return RecordProductionOrderCompletion(
            order_repo,
            self.lot_repo,
            file_repo or FakeProductionOrderFileRepository(),
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(order_repo, self.lot_repo, self.bus),
            **completion_collaborators(order_repo),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=RecordingLotCreation(),
        )

    async def test_partial_completion_updates_order_and_position(self):
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = self._use_case(order_repo)
        cmd = RecordProductionOrderCompletionCommand(quantity=3.0, completion_date=date(2026, 1, 2))
        result = await use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        assert result.quantity_completed == 3.0
        assert result.status == ProductionOrderStatus.IN_PROGRESS.value
        assert (await self.lot_repo.get_position_by_id(1)).quantity_completed == 3.0

    async def test_completes_machineless_order_on_pure_manual_position(self):
        # A machine-less order on a pure-manual position starts without a
        # machine (see StartProductionOrder), recording completions on it
        # must work too, all the way to COMPLETED.
        self.position.steps = [make_step(id=1, fabrication_method_requires_machine=False)]
        await self.lot_repo.save(self.lot)
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    machine_id=None,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = self._use_case(order_repo)
        cmd = RecordProductionOrderCompletionCommand(
            quantity=10.0, completion_date=date(2026, 1, 2)
        )
        result = await use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        assert result.status == ProductionOrderStatus.COMPLETED.value
        assert result.machine_id is None
        completed = [e for e in self.bus.published if isinstance(e, ProductionOrderCompleted)]
        assert len(completed) == 1
        assert completed[0].machine_id is None

    async def test_reads_the_lot_with_a_row_lock(self):
        """Two concurrent completions against sibling orders on the
        same lot must not both read the pre-write position total, see
        IProductionLotRepository.get_by_id_for_update."""
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = self._use_case(order_repo)
        cmd = RecordProductionOrderCompletionCommand(quantity=3.0, completion_date=date(2026, 1, 2))
        await use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        assert self.lot_repo.for_update_calls == [self.lot.id]

    async def test_order_level_cap_rejects_overflow(self):
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = self._use_case(order_repo)
        cmd = RecordProductionOrderCompletionCommand(
            quantity=11.0, completion_date=date(2026, 1, 2)
        )
        with pytest.raises(ProductionOrderQuantityOverflowError):
            await use_case.execute(self.actor, production_order_id=1, cmd=cmd)

    async def test_position_level_cap_aggregates_across_sibling_orders(self):
        """Two orders (6 + 4 = 10) on the same INTERNAL position. Position
        1's available input is its own quantity. When that is smaller than
        the sum of the order quantities, the position-level cap (not the
        order-level cap) must catch the overflow."""
        small_lot_position = make_position(
            id=2, lot_id=2, quantity=8.0, kind=LotPositionKind.INTERNAL
        )
        small_lot = make_lot(id=2, quantity=8.0, positions=[small_lot_position])
        small_lot.source_made_item_id = 99  # rework, exempt from raw-material gating
        lot_repo = FakeProductionLotRepository([small_lot])
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=2,
                    quantity=6.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                ),
                make_order(
                    id=2,
                    lot_position_id=2,
                    quantity=4.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                ),
            ]
        )
        use_case = RecordProductionOrderCompletion(
            order_repo,
            lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(order_repo, lot_repo, self.bus),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **completion_collaborators(order_repo),
        )
        # Order 1 completes all 6, position total 6, within lot quantity 8.
        await use_case.execute(
            self.actor,
            production_order_id=1,
            cmd=RecordProductionOrderCompletionCommand(
                quantity=6.0, completion_date=date(2026, 1, 2)
            ),
        )
        # Order 2 completing all 4 would bring the position total to 10,
        # exceeding the lot's available input of 8, position-level cap,
        # NOT order-level (order 2's own quantity of 4 is not exceeded).
        with pytest.raises(LotPositionOverflowError):
            await use_case.execute(
                self.actor,
                production_order_id=2,
                cmd=RecordProductionOrderCompletionCommand(
                    quantity=4.0, completion_date=date(2026, 1, 2)
                ),
            )

    async def test_final_completion_transitions_order_and_publishes_completed_event(self):
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = self._use_case(order_repo)
        cmd = RecordProductionOrderCompletionCommand(
            quantity=10.0, completion_date=date(2026, 1, 2)
        )
        result = await use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        assert result.status == ProductionOrderStatus.COMPLETED.value
        assert result.actual_end is not None
        assert any(isinstance(e, ProductionOrderCompleted) for e in self.bus.published)

    async def test_lot_completes_when_last_position_completes(self):
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = self._use_case(order_repo)
        await use_case.execute(
            self.actor,
            production_order_id=1,
            cmd=RecordProductionOrderCompletionCommand(
                quantity=10.0, completion_date=date(2026, 1, 2)
            ),
        )
        assert (await self.lot_repo.get_by_id(1)).status == LotStatus.COMPLETED.value

    async def test_rejects_completion_on_non_in_progress_order(self):
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.QUEUED,
                )
            ]
        )
        use_case = self._use_case(order_repo)
        cmd = RecordProductionOrderCompletionCommand(quantity=1.0, completion_date=date(2026, 1, 2))
        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await use_case.execute(self.actor, production_order_id=1, cmd=cmd)

    async def test_shared_account_requires_operator(self):
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = self._use_case(order_repo)
        shared_actor = make_user(
            id=2, permissions=[Permission.WRITE_PRODUCTION_ORDERS], is_shared_account=True
        )
        cmd = RecordProductionOrderCompletionCommand(quantity=1.0, completion_date=date(2026, 1, 2))
        with pytest.raises(OperatorSelectionRequiredError):
            await use_case.execute(shared_actor, production_order_id=1, cmd=cmd)

    async def test_personal_account_defaults_operator_to_self(self):
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = self._use_case(order_repo)
        cmd = RecordProductionOrderCompletionCommand(quantity=1.0, completion_date=date(2026, 1, 2))
        await use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        completions = await order_repo.get_completions(1)
        assert completions[0].operator_id == self.actor.id
        assert completions[0].recorded_by_id == self.actor.id

    async def test_raw_material_caps_position_one_completion(self):
        # self.position is sequence=1, INTERNAL, the exact shape raw
        # material capping applies to. Lot has a linked demand with only
        # 4.0 arrived so far.
        self.lot.source_made_item_id = None
        self.lot.input_demand_id = 42
        self.lot_repo = FakeProductionLotRepository(
            [self.lot], raw_material_arrived_by_demand={42: 4.0}
        )
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = RecordProductionOrderCompletion(
            order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(order_repo, self.lot_repo, self.bus),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **completion_collaborators(order_repo),
        )
        # Within what's arrived, succeeds.
        await use_case.execute(
            self.actor,
            production_order_id=1,
            cmd=RecordProductionOrderCompletionCommand(
                quantity=4.0, completion_date=date(2026, 1, 2)
            ),
        )
        assert (await self.lot_repo.get_position_by_id(1)).quantity_completed == 4.0

    async def test_raw_material_rejects_completion_beyond_arrived(self):
        self.lot.source_made_item_id = None
        self.lot.input_demand_id = 42
        self.lot_repo = FakeProductionLotRepository(
            [self.lot], raw_material_arrived_by_demand={42: 4.0}
        )
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = RecordProductionOrderCompletion(
            order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(order_repo, self.lot_repo, self.bus),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **completion_collaborators(order_repo),
        )
        with pytest.raises(LotPositionOverflowError):
            await use_case.execute(
                self.actor,
                production_order_id=1,
                cmd=RecordProductionOrderCompletionCommand(
                    quantity=5.0, completion_date=date(2026, 1, 2)
                ),
            )

    async def test_raw_material_zero_arrived_blocks_any_completion(self):
        self.lot.source_made_item_id = None
        self.lot.input_demand_id = 42
        self.lot_repo = FakeProductionLotRepository([self.lot], raw_material_arrived_by_demand={})
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = RecordProductionOrderCompletion(
            order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(order_repo, self.lot_repo, self.bus),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **completion_collaborators(order_repo),
        )
        with pytest.raises(LotPositionOverflowError):
            await use_case.execute(
                self.actor,
                production_order_id=1,
                cmd=RecordProductionOrderCompletionCommand(
                    quantity=1.0, completion_date=date(2026, 1, 2)
                ),
            )

    async def test_no_linked_demand_is_unaffected_by_raw_material_cap(self):
        # self.lot.input_demand_id is None by default, so the completion
        # is capped only by the lot quantity.
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = self._use_case(order_repo)
        await use_case.execute(
            self.actor,
            production_order_id=1,
            cmd=RecordProductionOrderCompletionCommand(
                quantity=10.0, completion_date=date(2026, 1, 2)
            ),
        )
        assert (await self.lot_repo.get_position_by_id(1)).quantity_completed == 10.0

    # ── QA/inspection split, permission, evidence, processed-based cap ──

    def _inspection_position(self, requires_evidence: bool = False):
        position = make_position(
            id=1,
            quantity=10.0,
            kind=LotPositionKind.INTERNAL,
            steps=[
                make_step(
                    id=1,
                    position_id=1,
                    fabrication_method_id=None,
                    role=StepRole.INSPECTION,
                    inspection_method_id=1,
                    inspection_method_name="Measurement"
                    if requires_evidence
                    else "Visual Inspection",
                    inspection_method_requires_evidence=requires_evidence,
                    fabrication_method_requires_machine=False,
                )
            ],
        )
        lot = make_lot(positions=[position])
        lot.source_made_item_id = 99
        self.lot_repo = FakeProductionLotRepository([lot])
        return position, lot

    async def test_accepted_only_propagation(self):
        # Only an inspection may reject pieces, and its disposition accounts
        # for every rejected one.
        self._inspection_position()
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = self._use_case(order_repo)
        cmd = RecordProductionOrderCompletionCommand(
            quantity=6.0,
            quantity_accepted=4.0,
            quantity_rejected=2.0,
            quantity_scrap=2.0,
            completion_date=date(2026, 1, 2),
        )
        result = await use_case.execute(_INSPECTOR, production_order_id=1, cmd=cmd)
        # order.quantity_completed only moved by the accepted 4.0, not the
        # full 6.0 batch.
        assert result.quantity_completed == 4.0
        assert (await self.lot_repo.get_position_by_id(1)).quantity_completed == 4.0
        completion = (await order_repo.get_completions(1))[0]
        assert completion.quantity == 6.0
        assert completion.quantity_accepted == 4.0
        assert completion.quantity_rejected == 2.0

    async def test_all_rejects_completes_order_without_moving_quantity_completed(self):
        self._inspection_position()
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=5.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = self._use_case(order_repo)
        cmd = RecordProductionOrderCompletionCommand(
            quantity=5.0,
            quantity_accepted=0.0,
            quantity_rejected=5.0,
            quantity_scrap=5.0,
            completion_date=date(2026, 1, 2),
        )
        result = await use_case.execute(_INSPECTOR, production_order_id=1, cmd=cmd)
        # Processed-based completeness: 0 accepted + 5 rejected = 5 = quantity,
        # order still completes even though quantity_completed never moved.
        assert result.status == ProductionOrderStatus.COMPLETED.value
        assert result.quantity_completed == 0.0

    async def test_split_sum_mismatch_raises(self):
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = self._use_case(order_repo)
        cmd = RecordProductionOrderCompletionCommand(
            quantity=6.0,
            quantity_accepted=4.0,
            quantity_rejected=1.0,  # 4 + 1 != 6
            completion_date=date(2026, 1, 2),
        )
        with pytest.raises(ProductionOrderCompletionSplitInvalidError):
            await use_case.execute(self.actor, production_order_id=1, cmd=cmd)

    async def test_inspection_position_requires_write_inspections_permission(self):
        self._inspection_position()
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = self._use_case(order_repo)
        cmd = RecordProductionOrderCompletionCommand(quantity=5.0, completion_date=date(2026, 1, 2))
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(self.actor, production_order_id=1, cmd=cmd)

    async def test_inspection_position_succeeds_with_write_inspections_permission(self):
        self._inspection_position()
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        inspector = make_user(
            id=2,
            permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.WRITE_INSPECTIONS],
        )
        use_case = self._use_case(order_repo)
        cmd = RecordProductionOrderCompletionCommand(
            quantity=5.0,
            quantity_accepted=5.0,
            quantity_rejected=0.0,
            completion_date=date(2026, 1, 2),
        )
        result = await use_case.execute(inspector, production_order_id=1, cmd=cmd)
        assert result.quantity_completed == 5.0

    async def test_ordinary_position_needs_no_write_inspections_permission(self):
        # self.position (default fixture) is an ordinary fabrication
        # position; self.actor only holds WRITE_PRODUCTION_ORDERS.
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = self._use_case(order_repo)
        cmd = RecordProductionOrderCompletionCommand(quantity=5.0, completion_date=date(2026, 1, 2))
        result = await use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        assert result.quantity_completed == 5.0

    async def test_measurement_inspection_without_evidence_file_rejected(self):
        self._inspection_position(requires_evidence=True)
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        inspector = make_user(
            id=2,
            permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.WRITE_INSPECTIONS],
        )
        use_case = self._use_case(order_repo, FakeProductionOrderFileRepository([]))
        cmd = RecordProductionOrderCompletionCommand(quantity=5.0, completion_date=date(2026, 1, 2))
        with pytest.raises(ProductionOrderMeasurementEvidenceRequiredError):
            await use_case.execute(inspector, production_order_id=1, cmd=cmd)

    async def test_visual_inspection_without_evidence_file_is_fine(self):
        self._inspection_position(requires_evidence=False)
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        inspector = make_user(
            id=2,
            permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.WRITE_INSPECTIONS],
        )
        use_case = self._use_case(order_repo, FakeProductionOrderFileRepository([]))
        cmd = RecordProductionOrderCompletionCommand(quantity=5.0, completion_date=date(2026, 1, 2))
        result = await use_case.execute(inspector, production_order_id=1, cmd=cmd)
        assert result.quantity_completed == 5.0

    async def test_measurement_inspection_with_evidence_file_succeeds(self):
        self._inspection_position(requires_evidence=True)
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        inspector = make_user(
            id=2,
            permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.WRITE_INSPECTIONS],
        )
        file_repo = FakeProductionOrderFileRepository(
            [
                ProductionOrderFile(
                    id=0,
                    production_order_id=1,
                    file_name="report.pdf",
                    stored_name="abc.pdf",
                    mime_type="application/pdf",
                    size_bytes=123,
                    storage_path="production_orders/1/measurement_report/abc.pdf",
                    sha256="x",
                    category=ProductionOrderFileCategory.MEASUREMENT_REPORT,
                    created=datetime(2026, 1, 2, tzinfo=UTC),
                    uploaded_by_user_id=2,
                )
            ]
        )
        use_case = self._use_case(order_repo, file_repo)
        cmd = RecordProductionOrderCompletionCommand(quantity=5.0, completion_date=date(2026, 1, 2))
        result = await use_case.execute(inspector, production_order_id=1, cmd=cmd)
        assert result.quantity_completed == 5.0

    async def test_evidence_is_looked_up_under_the_order_lock(self):
        """An evidence delete locks the production order too, so the lookup
        has to come after the completion took that lock."""
        self._inspection_position(requires_evidence=True)
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        locks_at_lookup: list[list[list[int]]] = []

        class _WatchingFileRepo(FakeProductionOrderFileRepository):
            async def get_by_item_id_and_category(self, item_id, category):
                locks_at_lookup.append(list(order_repo.lock_calls))
                return await super().get_by_item_id_and_category(item_id, category)

        inspector = make_user(
            id=2,
            permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.WRITE_INSPECTIONS],
        )
        use_case = self._use_case(order_repo, _WatchingFileRepo([]))
        cmd = RecordProductionOrderCompletionCommand(quantity=5.0, completion_date=date(2026, 1, 2))
        with pytest.raises(ProductionOrderMeasurementEvidenceRequiredError):
            await use_case.execute(inspector, production_order_id=1, cmd=cmd)

        assert locks_at_lookup == [[[1]]]

    async def test_inspection_recorded_event_emitted_for_inspection_position(self):
        self._inspection_position()
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        inspector = make_user(
            id=2,
            permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.WRITE_INSPECTIONS],
        )
        use_case = self._use_case(order_repo)
        cmd = RecordProductionOrderCompletionCommand(
            quantity=5.0,
            quantity_accepted=3.0,
            quantity_rejected=2.0,
            quantity_rework=1.0,
            quantity_scrap=1.0,
            completion_date=date(2026, 1, 2),
        )
        await use_case.execute(inspector, production_order_id=1, cmd=cmd)
        events = await self.lot_repo.get_events(1)
        inspection_events = [e for e in events if e.event_type == LotEventType.INSPECTION_RECORDED]
        assert len(inspection_events) == 1
        assert inspection_events[0].payload["quantity_accepted"] == 3.0
        assert inspection_events[0].payload["quantity_rejected"] == 2.0

    async def test_no_inspection_recorded_event_for_ordinary_position(self):
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = self._use_case(order_repo)
        cmd = RecordProductionOrderCompletionCommand(quantity=5.0, completion_date=date(2026, 1, 2))
        await use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        events = await self.lot_repo.get_events(1)
        assert not any(e.event_type == LotEventType.INSPECTION_RECORDED for e in events)
