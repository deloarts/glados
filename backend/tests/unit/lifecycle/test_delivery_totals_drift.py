"""
LifecycleDriftReport on the fake world with a delivery repository: an order
line whose stored delivery totals differ from the sums over its delivery
rows is a fact anomaly, one row per differing total. Without a delivery
repository, or without order lines among the chosen tables, the totals are
not read.
"""

import dataclasses

from src.modules.fulfillment.application.services.lifecycle_drift import LifecycleDriftReport
from src.modules.fulfillment.application.services.lifecycle_loader import LifecycleRepositories
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.services.lifecycle.delivery_totals import DELIVERY_TOTALS_RULE
from src.modules.fulfillment.domain.services.lifecycle.delivery_totals import DeliveryTotals
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from tests.unit.lifecycle.fake_world import NOW
from tests.unit.lifecycle.fake_world import FakeWorld


class _Deliveries:
    """The totals the delivery rows add up to, per line, and the lines asked
    for."""

    def __init__(self, totals: dict[int, DeliveryTotals]) -> None:
        self._totals = totals
        self.asked: list[list[int]] = []

    async def get_totals_by_order_item_ids(
        self, order_item_ids: list[int]
    ) -> dict[int, DeliveryTotals]:
        self.asked.append(sorted(order_item_ids))
        return {i: totals for i, totals in self._totals.items() if i in order_item_ids}


def _partially_delivered_line() -> tuple[FakeWorld, OrderItem]:
    """An order with one line that stores four of ten pieces delivered."""
    world = FakeWorld()
    order = world.order(status=OrderStatus.PARTIALLY_DELIVERED, ordered_date=NOW)
    line = world.line(
        order, status=OrderItemStatus.PARTIALLY_DELIVERED, ordered_date=NOW, delivered=4.0
    )
    return world, line


def _with(world: FakeWorld, deliveries: _Deliveries) -> LifecycleRepositories:
    return dataclasses.replace(world.repositories, deliveries=deliveries)


async def test_a_line_whose_rows_add_up_to_its_totals_is_no_anomaly() -> None:
    world, line = _partially_delivered_line()
    deliveries = _Deliveries({line.id: DeliveryTotals(accepted=4.0)})

    report = await LifecycleDriftReport(_with(world, deliveries)).run()

    assert report.rows == []
    assert deliveries.asked == [[line.id]]


async def test_a_total_without_its_rows_is_a_fact_anomaly_of_the_line() -> None:
    world, line = _partially_delivered_line()

    report = await LifecycleDriftReport(_with(world, _Deliveries({}))).run()

    (row,) = report.rows
    assert (row.table, row.id, row.public_id, row.field, row.stored, row.derived) == (
        "order_items",
        line.id,
        line.public_id,
        "quantity_delivered",
        "4",
        "0",
    )
    assert (row.rule, row.anomaly) == (DELIVERY_TOTALS_RULE, True)
    assert row.facts["delivered"] == 4.0
    assert report.tallies["order_items"].drift == 1


async def test_rows_without_their_booking_differ_in_each_total_they_carry() -> None:
    world, line = _partially_delivered_line()
    rows = DeliveryTotals(accepted=4.0, rejected=3.0, lost=1.0)

    report = await LifecycleDriftReport(_with(world, _Deliveries({line.id: rows}))).run()

    assert [(r.field, r.stored, r.derived) for r in report.rows] == [
        ("quantity_rejected", "0", "3"),
        ("quantity_rejected_lost", "0", "1"),
    ]


async def test_without_a_delivery_repository_the_totals_are_not_compared() -> None:
    world, _line = _partially_delivered_line()

    report = await LifecycleDriftReport(world.repositories).run()

    assert report.rows == []


async def test_the_totals_are_read_only_when_order_lines_are_chosen() -> None:
    world, _line = _partially_delivered_line()
    deliveries = _Deliveries({})

    report = await LifecycleDriftReport(_with(world, deliveries)).run([LifecycleAggregate.ORDERS])

    assert report.rows == []
    assert deliveries.asked == []
