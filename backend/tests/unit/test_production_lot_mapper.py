"""
Unit tests for LotMapper.to_summary's per-step position enrichment
(position_kind, position_needs_machine), the lots-list feature needs this
to know, without a full-lot fetch, whether a step's position is still
assignable (kind == unassigned) or an already-internal position still
needs a machine (nullable ProductionOrder.machine_id).
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.fulfillment.application.mappers.production_lot_mapper import LotMapper
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.value_objects.localized_text import LocalizedText


def make_step(id: int, position_id: int, sequence: int = 1) -> LotStep:
    return LotStep(
        id=id,
        created=date(2026, 1, 1),
        note=None,
        estimated_setup_minutes=10,
        estimated_minutes_per_piece=2.0,
        sequence=sequence,
        creator_id=1,
        fabrication_method_id=1,
        lot_id=1,
        position_id=position_id,
        source_process_id=None,
        fabrication_method_name=LocalizedText({"enGB": "Milling"}),
    )


def make_position(
    id: int,
    kind: LotPositionKind,
    steps: list[LotStep],
    production_orders: list[ProductionOrder] | None = None,
    status: LotPositionStatus = LotPositionStatus.PENDING,
    quantity: float = 10.0,
) -> LotPosition:
    return LotPosition(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        sequence=id,
        kind=kind,
        status=status,
        quantity=quantity,
        quantity_completed=0.0,
        note=None,
        creator_id=1,
        lot_id=1,
        steps=steps,
        production_orders=production_orders or [],
    )


def make_production_order(
    id: int,
    position_id: int,
    machine_id: int | None,
    quantity: float = 10.0,
    machine_pool_id: int | None = None,
    machine_pool_name: str = "",
) -> ProductionOrder:
    return ProductionOrder(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        production_order_number=f"PO-{id}",
        status=ProductionOrderStatus.QUEUED,
        priority=UrgencyClass.NORMAL,
        pinned=False,
        queue_sequence=1,
        quantity=quantity,
        quantity_completed=0.0,
        estimated_duration_minutes=30,
        note=None,
        planned_start=None,
        planned_end=None,
        not_before=None,
        actual_start=None,
        actual_end=None,
        creator_id=1,
        machine_id=machine_id,
        machine_pool_id=machine_pool_id,
        machine_pool_name=machine_pool_name,
        lot_position_id=position_id,
    )


def make_lot(positions: list[LotPosition]) -> ProductionLot:
    flat_steps = sorted(
        (step for position in positions for step in position.steps), key=lambda s: s.sequence
    )
    return ProductionLot(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        lot_number="LOT-0001",
        quantity=10.0,
        status=LotStatus.PARTIALLY_PLANNED,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=None,
        positions=positions,
        steps=flat_steps,
    )


class TestLotMapperToSummary:
    def test_unassigned_position_step(self):
        step = make_step(id=1, position_id=1)
        position = make_position(id=1, kind=LotPositionKind.UNASSIGNED, steps=[step])
        lot = make_lot([position])

        result = LotMapper.to_summary(lot)

        assert result.steps[0].position_kind == LotPositionKind.UNASSIGNED.value
        assert result.steps[0].position_needs_machine is False

    def test_carries_position_status_through(self):
        step = make_step(id=1, position_id=1)
        position = make_position(
            id=1,
            kind=LotPositionKind.EXTERNAL,
            steps=[step],
            status=LotPositionStatus.COMPLETED,
        )
        lot = make_lot([position])

        result = LotMapper.to_summary(lot)

        assert result.steps[0].position_status == LotPositionStatus.COMPLETED.value

    def test_carries_partial_allocation_quantity_through(self):
        step = make_step(id=1, position_id=1)
        order = make_production_order(id=1, position_id=1, machine_id=5, quantity=3.0)
        position = make_position(
            id=1,
            kind=LotPositionKind.INTERNAL,
            steps=[step],
            production_orders=[order],
            quantity=4.0,
        )
        lot = make_lot([position])

        result = LotMapper.to_summary(lot)

        assert result.steps[0].position_quantity == 4.0
        assert result.steps[0].position_quantity_remaining == 1.0

    def test_unassigned_position_step_reports_full_remaining_quantity(self):
        step = make_step(id=1, position_id=1)
        position = make_position(id=1, kind=LotPositionKind.UNASSIGNED, steps=[step], quantity=4.0)
        lot = make_lot([position])

        result = LotMapper.to_summary(lot)

        assert result.steps[0].position_quantity == 4.0
        assert result.steps[0].position_quantity_remaining == 4.0

    def test_internal_position_fully_routed(self):
        step = make_step(id=1, position_id=1)
        order = make_production_order(id=1, position_id=1, machine_id=5)
        position = make_position(
            id=1, kind=LotPositionKind.INTERNAL, steps=[step], production_orders=[order]
        )
        lot = make_lot([position])

        result = LotMapper.to_summary(lot)

        assert result.steps[0].position_kind == LotPositionKind.INTERNAL.value
        assert result.steps[0].position_needs_machine is False

    def test_internal_position_with_unassigned_machine_order(self):
        step = make_step(id=1, position_id=1)
        order = make_production_order(id=1, position_id=1, machine_id=None)
        position = make_position(
            id=1, kind=LotPositionKind.INTERNAL, steps=[step], production_orders=[order]
        )
        lot = make_lot([position])

        result = LotMapper.to_summary(lot)

        assert result.steps[0].position_kind == LotPositionKind.INTERNAL.value
        assert result.steps[0].position_needs_machine is True

    def test_internal_position_partially_routed_d13_split(self):
        step = make_step(id=1, position_id=1)
        routed = make_production_order(id=1, position_id=1, machine_id=5)
        unrouted = make_production_order(id=2, position_id=1, machine_id=None)
        position = make_position(
            id=1,
            kind=LotPositionKind.INTERNAL,
            steps=[step],
            production_orders=[routed, unrouted],
        )
        lot = make_lot([position])

        result = LotMapper.to_summary(lot)

        assert result.steps[0].position_needs_machine is True

    def test_external_position_never_needs_machine(self):
        step = make_step(id=1, position_id=1)
        position = make_position(id=1, kind=LotPositionKind.EXTERNAL, steps=[step])
        lot = make_lot([position])

        result = LotMapper.to_summary(lot)

        assert result.steps[0].position_kind == LotPositionKind.EXTERNAL.value
        assert result.steps[0].position_needs_machine is False

    def test_multiple_positions_each_step_gets_its_own_position_kind(self):
        step_a = make_step(id=1, position_id=1, sequence=1)
        step_b = make_step(id=2, position_id=2, sequence=2)
        position_a = make_position(id=1, kind=LotPositionKind.UNASSIGNED, steps=[step_a])
        position_b = make_position(id=2, kind=LotPositionKind.EXTERNAL, steps=[step_b])
        lot = make_lot([position_a, position_b])

        result = LotMapper.to_summary(lot)

        by_position_id = {s.position_id: s for s in result.steps}
        assert by_position_id[1].position_kind == LotPositionKind.UNASSIGNED.value
        assert by_position_id[2].position_kind == LotPositionKind.EXTERNAL.value


class TestLotMapperToResultPositions:
    """LotMapper.to_result (the single-lot "detail" endpoint) embeds the
    FULL ProductionOrderResult per position, which already carries
    machine_pool_id/machine_pool_name (see ProductionOrderMapper.to_result);
    unlike the trimmed LotSummaryProductionOrderResult the lots list uses,
    no separate wiring is needed here. This pins that down."""

    def test_carries_pool_assignment_through(self):
        step = make_step(id=1, position_id=1)
        order = make_production_order(
            id=5,
            position_id=1,
            machine_id=None,
            machine_pool_id=3,
            machine_pool_name="3-Axis Pool",
        )
        position = make_position(
            id=1,
            kind=LotPositionKind.INTERNAL,
            steps=[step],
            production_orders=[order],
        )
        lot = make_lot([position])

        result = LotMapper.to_result(lot)

        detail_order = result.positions[0].production_orders[0]
        assert detail_order.machine_pool_id == 3
        assert detail_order.machine_pool_name == "3-Axis Pool"


class TestLotMapperToSummaryPositions:
    """The lots list resolves every step's planned/delivery date from these
    positions. They exist so the client needs no follow-up fetch per lot
    (and no fetch of each linked Order behind it) just to render a date;
    see LotSummaryPositionResult."""

    def test_inlines_order_item_delivery_facts(self):
        step = make_step(id=1, position_id=1)
        position = make_position(id=1, kind=LotPositionKind.EXTERNAL, steps=[step])
        position.order_item_id = 7
        position.order_id = 3
        position.order_number = "ORD-3"
        position.order_item_status = OrderItemStatus.DELIVERED
        position.order_item_quantity = 10.0
        position.order_item_quantity_delivered = 10.0
        position.order_item_unit = "pcs"
        position.order_item_items_per_unit = 1.0
        position.expected_delivery_date = date(2026, 2, 1)
        # Delivery/pickup are recorded events, so they carry a time of day;
        # expected_delivery_date above is a target and stays a plain date.
        position.order_item_delivery_date = datetime(2026, 2, 3, 14, 30, tzinfo=UTC)
        position.order_item_ready_for_pickup_date = datetime(2026, 2, 2, 9, 15, tzinfo=UTC)
        position.order_item_delivery_record_count = 2
        position.order_item_ordered_by_name = "Jane Doe"
        lot = make_lot([position])

        result = LotMapper.to_summary(lot)

        assert len(result.positions) == 1
        summary_position = result.positions[0]
        assert summary_position.order_id == 3
        assert summary_position.order_number == "ORD-3"
        assert summary_position.order_item_id == 7
        assert summary_position.order_item_status == "delivered"
        assert summary_position.expected_delivery_date == date(2026, 2, 1)
        assert summary_position.delivery_date == datetime(2026, 2, 3, 14, 30, tzinfo=UTC)
        assert summary_position.ready_for_pickup_date == datetime(2026, 2, 2, 9, 15, tzinfo=UTC)
        assert summary_position.delivery_record_count == 2
        assert summary_position.ordered_by_name == "Jane Doe"
        assert summary_position.order_item_unit == "pcs"

    def test_carries_production_order_schedule_and_conflicts(self):
        step = make_step(id=1, position_id=1)
        order = make_production_order(id=5, position_id=1, machine_id=None)
        position = make_position(
            id=1,
            kind=LotPositionKind.INTERNAL,
            steps=[step],
            production_orders=[order],
        )
        lot = make_lot([position])

        result = LotMapper.to_summary(lot, {5: ["no_machine_assigned"]})

        summary_order = result.positions[0].production_orders[0]
        assert summary_order.id == 5
        assert summary_order.status == ProductionOrderStatus.QUEUED.value
        assert summary_order.conflicts == ["no_machine_assigned"]
        # Never pinned by a person; the client renders "Auto-planner".
        assert summary_order.planned_by_name is None

    def test_carries_pool_assignment_through(self):
        """A pool-assigned-unresolved order (machine_id None, machine_pool_id
        set) must surface both pool fields on the summary production order,
        or the lots list has nothing to render but "Not assigned"."""
        step = make_step(id=1, position_id=1)
        order = make_production_order(
            id=5,
            position_id=1,
            machine_id=None,
            machine_pool_id=3,
            machine_pool_name="3-Axis Pool",
        )
        position = make_position(
            id=1,
            kind=LotPositionKind.INTERNAL,
            steps=[step],
            production_orders=[order],
        )
        lot = make_lot([position])

        result = LotMapper.to_summary(lot)

        summary_order = result.positions[0].production_orders[0]
        assert summary_order.machine_pool_id == 3
        assert summary_order.machine_pool_name == "3-Axis Pool"

    def test_conflicts_default_to_empty_when_not_computed(self):
        step = make_step(id=1, position_id=1)
        order = make_production_order(id=5, position_id=1, machine_id=1)
        position = make_position(
            id=1,
            kind=LotPositionKind.INTERNAL,
            steps=[step],
            production_orders=[order],
        )
        lot = make_lot([position])

        result = LotMapper.to_summary(lot)

        assert result.positions[0].production_orders[0].conflicts == []

    def test_source_material_rides_along_for_the_mismatch_warning(self):
        step = make_step(id=1, position_id=1)
        lot = make_lot([make_position(id=1, kind=LotPositionKind.UNASSIGNED, steps=[step])])
        lot.made_item_material = "1.0037"
        lot.source_material = "1.4301"

        result = LotMapper.to_summary(lot)

        assert result.source_material == "1.4301"
