"""
An allocation never covers more than its own quantity. A line or a lot can
report more pieces than its quantity, for example a line whose quantity was
lowered below what it had already received. Such a source covers its
allocations fully and never more, so a demand cannot read as delivered
beyond what its allocations and stock actually hold. Pieces lost at receipt
never count as arrived.
"""

from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.services.allocation_coverage import CoverageInfo
from src.modules.fulfillment.domain.services.allocation_coverage import OrderItemCoverageSource
from src.modules.fulfillment.domain.services.allocation_coverage import compute_coverage_totals
from src.modules.fulfillment.domain.services.allocation_service import AllocationQuantityService
from src.modules.fulfillment.domain.services.lifecycle.demand import BOUGHT_DEMAND_STATUS
from src.modules.fulfillment.domain.services.lifecycle.facts import AllocationFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import CoveringLineFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import DemandFacts
from src.modules.fulfillment.domain.services.lot_rules import build_lot_coverage
from src.modules.fulfillment.domain.services.made_item_allocation_service import (
    MadeItemAllocationQuantityService,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass


def make_line(
    *, id: int = 1, quantity: float, delivered: float, lost: float = 0.0, status: OrderItemStatus
) -> OrderItem:
    return OrderItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        status=status,
        quantity=quantity,
        quantity_delivered=delivered,
        unit="pcs",
        items_per_unit=1.0,
        price=None,
        note=None,
        ordered_date=None,
        expected_delivery_date=None,
        delivery_date=None,
        storage_place=None,
        expected_pickup_date=None,
        ready_for_pickup_date=None,
        position=1,
        creator_id=1,
        orderer_id=None,
        receiver_id=None,
        bought_item_id=1,
        order_id=1,
        supplier_id=1,
        project_id=1,
        line_type=OrderLineType.BOUGHT,
        lot_position_id=None,
        source_item_id=None,
        quantity_rejected=lost,
        quantity_rejected_lost=lost,
    )


@dataclass
class _Alloc:
    quantity: float
    source: str
    coverage_ref_id: int | None
    demand_item_id: int = 1


class _FixedCoverageSource:
    def __init__(self, coverage: dict[int, CoverageInfo]) -> None:
        self._coverage = coverage

    def coverage_for(self, ref_id: int) -> CoverageInfo | None:
        return self._coverage.get(ref_id)


class TestOrderItemCoverageSource:
    def test_a_line_delivered_past_its_quantity_reports_what_it_received(self):
        line = make_line(quantity=4.0, delivered=6.0, status=OrderItemStatus.DELIVERED)

        info = OrderItemCoverageSource({1: line}).coverage_for(1)

        assert info is not None
        assert info.arrived == 6.0

    def test_lost_pieces_never_count_as_arrived(self):
        line = make_line(quantity=4.0, delivered=3.0, lost=3.0, status=OrderItemStatus.DELIVERED)

        info = OrderItemCoverageSource({1: line}).coverage_for(1)

        assert info is not None
        assert info.arrived == 3.0

    def test_a_partial_delivery_reports_its_accepted_pieces(self):
        line = make_line(quantity=10.0, delivered=6.0, status=OrderItemStatus.PARTIALLY_DELIVERED)

        info = OrderItemCoverageSource({1: line}).coverage_for(1)

        assert info is not None
        assert info.arrived == 6.0


class TestCoverageTotals:
    def test_a_source_reporting_more_than_its_quantity_covers_the_allocation_once(self):
        allocations = [_Alloc(quantity=10.0, source="order", coverage_ref_id=1)]
        coverage = _FixedCoverageSource({1: CoverageInfo(is_placed=True, arrived=15.0)})

        allocated, ordered, delivered, from_stock = compute_coverage_totals(
            allocations, coverage, stock_source_value="stock", rank=0, fill={}
        )

        assert (allocated, ordered, delivered, from_stock) == (10.0, 10.0, 10.0, 0.0)

    def test_a_demand_on_an_overdelivered_line_is_not_fulfilled_beyond_its_pieces(self):
        # 6 allocated on a line cut to 4 after it received 6, plus 2 from
        # stock: 8 real pieces for a demand of 10. Uncapped, the line's 6
        # received pieces would read as more than the allocation holds.
        demand = BoughtItemDemandItem(
            id=1,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            status=BoughtItemDemandStatus.ORDERED,
            quantity=10.0,
            unit="pcs",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=None,
            desired_delivery_date=None,
            creator_id=1,
            item_id=1,
            project_id=1,
        )
        allocations = [
            BoughtItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=6.0),
            BoughtItemDemandAllocation(
                demand_item_id=1, order_item_id=None, quantity=2.0, source=AllocationSource.STOCK
            ),
        ]
        line = make_line(quantity=4.0, delivered=6.0, status=OrderItemStatus.DELIVERED)

        summary = AllocationQuantityService.compute_summary(demand, allocations, {1: line}, {})

        assert summary.delivered == 6.0
        assert summary.fulfilled_from_stock == 2.0
        assert not summary.is_fully_delivered
        derived = BOUGHT_DEMAND_STATUS.derive(
            DemandFacts(
                quantity=demand.quantity,
                allocations=(
                    AllocationFacts.on_line(
                        6.0,
                        CoveringLineFacts(
                            status=OrderItemStatus.DELIVERED, quantity=4.0, delivered=6.0, lost=0.0
                        ),
                    ),
                    AllocationFacts.stock(2.0),
                ),
                canceled_at=None,
                fulfilled_manually_at=None,
            )
        )
        assert derived.value is BoughtItemDemandStatus.ALLOCATED

    def test_a_lot_reporting_more_than_its_quantity_covers_the_allocation_once(self):
        # 8 allocated on a lot of 8 whose last position reports 10: uncapped,
        # the 10 completed pieces would read as delivered and fulfil the demand.
        lot = ProductionLot(
            id=7,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=None,
            changes=[],
            lot_number="LOT-7",
            quantity=8.0,
            status=LotStatus.COMPLETED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=1,
            made_item_id=1,
            project_id=1,
            input_demand_id=None,
        )
        lot.positions = [
            LotPosition(
                id=1,
                created=datetime(2026, 1, 1, tzinfo=UTC),
                changed=None,
                changes=[],
                sequence=1,
                kind=LotPositionKind.INTERNAL,
                status=LotPositionStatus.COMPLETED,
                quantity=8.0,
                quantity_completed=10.0,
                note=None,
                creator_id=1,
                lot_id=7,
            )
        ]
        demand = MadeItemDemandItem(
            id=1,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            status=MadeItemDemandStatus.ORDERED,
            quantity=10.0,
            unit="pcs",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=None,
            desired_delivery_date=None,
            creator_id=1,
            made_item_id=1,
            project_id=1,
        )
        allocation = MadeItemDemandAllocation(demand_item_id=1, lot_id=7, quantity=8.0)

        summary = MadeItemAllocationQuantityService.compute_summary(
            demand, [allocation], build_lot_coverage([lot]), fill={}
        )

        assert summary.delivered == 8.0
        assert not summary.is_fully_delivered
