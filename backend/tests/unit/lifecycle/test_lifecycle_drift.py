"""
LifecycleDriftReport on the fake world: every stored lifecycle field that
differs from its derivation is one row with the rule and the facts, a
position completed beyond its quantity is a fact anomaly, the walk pages
through every table, and nothing is written or locked.
"""

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.services.lifecycle_drift import LifecycleDriftReport
from src.modules.fulfillment.domain.services.lifecycle.stored import COMPLETED_OVER_QUANTITY_RULE
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from tests.unit.lifecycle.fake_world import NOW
from tests.unit.lifecycle.fake_world import FakeWorld

_A = LifecycleAggregate


def _consistent_world() -> FakeWorld:
    world = FakeWorld()
    lot = world.lot(status=LotStatus.IN_PROGRESS)
    position = world.position(
        lot,
        kind=LotPositionKind.INTERNAL,
        status=LotPositionStatus.PARTIALLY_COMPLETED,
        quantity_completed=4.0,
    )
    world.production_order(
        position, status=ProductionOrderStatus.IN_PROGRESS, actual_start=NOW, processed=4.0
    )
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    line = world.line(order, status=OrderItemStatus.ORDERED, ordered_date=NOW)
    demand = world.bought_demand(status=BoughtItemDemandStatus.ORDERED)
    world.allocate_bought(demand, line, 10.0)
    world.made_demand(status=MadeItemDemandStatus.OPEN)
    world.source_demand(status=SourceItemDemandStatus.CANCELED, canceled_at=NOW)
    world.quote_request(status=QuoteRequestStatus.DRAFT)
    return world


async def test_a_consistent_world_has_no_drift_and_counts_what_it_checked() -> None:
    world = _consistent_world()

    report = await LifecycleDriftReport(world.repositories).run()

    assert report.rows == []
    assert not report.has_drift
    assert {name: tally.checked for name, tally in report.tallies.items()} == {
        "order_items": 1,
        "orders": 1,
        "production_orders": 1,
        "lot_positions": 1,
        "lots": 1,
        "bought_demands": 1,
        "made_demands": 1,
        "source_demands": 1,
        "quote_requests": 1,
    }
    assert (world.saves, world.lock_log) == ([], [])


async def test_each_differing_field_is_a_row_with_its_rule_and_facts() -> None:
    world = FakeWorld()
    lot = world.lot(status=LotStatus.DRAFT)
    position = world.position(
        lot, kind=LotPositionKind.UNASSIGNED, status=LotPositionStatus.PENDING
    )
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    world.line(
        order, status=OrderItemStatus.ORDERED, ordered_date=NOW, delivered=10.0, position=position
    )

    report = await LifecycleDriftReport(world.repositories).run()

    found = {(row.table, row.field): (row.stored, row.derived) for row in report.rows}
    assert found == {
        ("lots", "status"): ("draft", "completed"),
        ("lots", "completed_at"): ("-", "set"),
        ("lot_positions", "kind"): ("unassigned", "external"),
        ("lot_positions", "status"): ("pending", "completed"),
        ("lot_positions", "quantity_completed"): ("0", "10"),
        ("orders", "status"): ("ordered", "delivered"),
        ("orders", "delivery_date"): ("-", "set"),
        ("order_items", "status"): ("ordered", "delivered"),
    }
    lot_row = next(r for r in report.rows if (r.table, r.field) == ("lots", "status"))
    assert lot_row.rule.startswith("lot_status row 3: ")
    assert lot_row.facts["position_statuses"] == ["completed"]
    assert lot_row.public_id == lot.public_id
    assert report.tallies["lots"].drift == 2


async def test_a_position_completed_beyond_its_quantity_is_a_fact_anomaly() -> None:
    world = FakeWorld()
    lot = world.lot(quantity=10.0, status=LotStatus.COMPLETED, completed_at=NOW)
    position = world.position(
        lot,
        kind=LotPositionKind.INTERNAL,
        status=LotPositionStatus.COMPLETED,
        quantity_completed=10.0,
    )
    world.production_order(
        position,
        status=ProductionOrderStatus.COMPLETED,
        actual_start=NOW,
        actual_end=NOW,
        processed=12.0,
    )

    report = await LifecycleDriftReport(world.repositories).run()

    [row] = report.rows
    assert (row.table, row.field, row.stored, row.derived, row.anomaly) == (
        "lot_positions",
        "quantity_completed",
        "10",
        "12",
        True,
    )
    assert row.rule == COMPLETED_OVER_QUANTITY_RULE


async def test_stamps_are_compared() -> None:
    world = FakeWorld()
    world.order(status=OrderStatus.DRAFT, delivery_date=NOW)

    report = await LifecycleDriftReport(world.repositories).run()

    assert {(r.table, r.field, r.derived) for r in report.rows} == {
        ("orders", "delivery_date", "-"),
    }


async def test_the_report_walks_every_page() -> None:
    world = FakeWorld()
    for _ in range(3):
        world.order(status=OrderStatus.ORDERED)
        world.bought_demand(status=BoughtItemDemandStatus.ORDERED)

    report = await LifecycleDriftReport(world.repositories, batch_size=1).run()

    assert [r.table for r in report.rows].count("orders") == 3
    assert [r.table for r in report.rows].count("bought_demands") == 3


async def test_the_report_reads_only_the_chosen_tables() -> None:
    world = FakeWorld()
    lot = world.lot(status=LotStatus.PLANNED)
    world.position(lot)
    world.order(status=OrderStatus.ORDERED)

    report = await LifecycleDriftReport(world.repositories).run([_A.ORDERS])

    assert [r.table for r in report.rows] == ["orders"]
    assert set(report.tallies) == {"orders"}


async def test_a_line_on_a_lot_is_compared_once_through_its_order() -> None:
    world = FakeWorld()
    lot = world.lot()
    position = world.position(
        lot, kind=LotPositionKind.EXTERNAL, status=LotPositionStatus.ORDERED_OR_QUEUED
    )
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    world.line(order, status=OrderItemStatus.PENDING, ordered_date=NOW, position=position)

    report = await LifecycleDriftReport(world.repositories).run()

    assert [(r.table, r.field) for r in report.rows if r.table == "order_items"] == [
        ("order_items", "status")
    ]
    assert report.tallies["order_items"].checked == 1
