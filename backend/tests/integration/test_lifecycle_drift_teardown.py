"""
The drift check the suite runs after every test (conftest.py,
_lifecycle_drift.py): it fails on a stored lifecycle field that disagrees
with its derivation, for the aggregates it is given, and on an order line
whose delivery totals differ from its delivery rows, and it is given the
reconciler's RECONCILED_AGGREGATES as they are when it runs. A failing
teardown cannot be asserted from inside the test it follows, so these tests
call the check the teardown calls.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.application.services import lifecycle_reconciler
from src.modules.fulfillment.domain.services.lifecycle.delivery_totals import DELIVERY_TOTALS_RULE
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from tests.integration import _lifecycle_seed as seed
from tests.integration._lifecycle_drift import assert_no_lifecycle_drift
from tests.integration._lifecycle_drift import checked_aggregates
from tests.integration._lifecycle_drift import lifecycle_drift_rows

_A = LifecycleAggregate


async def test_the_check_fails_on_an_inconsistent_row_of_a_checked_aggregate(
    db: AsyncSession, allow_lifecycle_drift: None
) -> None:
    order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    canceled = await seed.line(db, order, "ordered", ordered_date=seed.NOW, canceled_at=seed.NOW)
    await db.commit()

    with pytest.raises(pytest.fail.Exception) as failed:
        await assert_no_lifecycle_drift({_A.ORDER_ITEMS})

    message = str(failed.value)
    assert f"order_items #{canceled.id} status: stored ordered, derived canceled" in message
    assert "allow_lifecycle_drift" in message


async def test_the_check_passes_consistent_rows(db: AsyncSession) -> None:
    order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    await seed.line(db, order, "ordered", ordered_date=seed.NOW)
    await db.commit()
    checked = {_A.ORDER_ITEMS, _A.ORDERS}

    # The check must not fail; the rows it would list are asserted empty too.
    await assert_no_lifecycle_drift(checked)
    assert await lifecycle_drift_rows(checked) == []


async def test_the_check_reads_only_the_aggregates_it_is_given(
    db: AsyncSession, allow_lifecycle_drift: None
) -> None:
    order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    await seed.line(db, order, "pending", ordered_date=seed.NOW)
    await db.commit()

    assert await lifecycle_drift_rows({_A.LOTS, _A.BOUGHT_DEMANDS}) == []
    assert [row.table for row in await lifecycle_drift_rows({_A.ORDER_ITEMS})] == ["order_items"]
    # No aggregate checked, nothing read: the state of the suite until the
    # first aggregate moves onto the reconciler.
    await assert_no_lifecycle_drift(frozenset())


async def test_the_check_reports_delivered_pieces_without_their_delivery_row(
    db: AsyncSession, allow_lifecycle_drift: None
) -> None:
    order = await seed.order(db, "delivered", ordered_date=seed.NOW, delivery_date=seed.NOW)
    line = await seed.line(
        db, order, "delivered", ordered_date=seed.NOW, quantity_delivered=10.0, booked=False
    )
    await db.commit()

    rows = await lifecycle_drift_rows(checked_aggregates())

    assert [(r.table, r.id, r.field, r.stored, r.derived, r.anomaly) for r in rows] == [
        ("order_items", line.id, "quantity_delivered", "10", "0", True)
    ]
    assert rows[0].rule == DELIVERY_TOTALS_RULE


async def test_the_check_reports_a_placed_order_without_its_ordered_date(
    db: AsyncSession, allow_lifecycle_drift: None
) -> None:
    # Every line is ordered, so the order derives ORDERED and its stored
    # status agrees. Only the date the reconciler records with it is missing.
    order = await seed.order(db, "ordered")
    await seed.line(db, order, "ordered", ordered_date=seed.NOW)
    await db.commit()

    rows = await lifecycle_drift_rows(checked_aggregates())

    assert [(r.table, r.id, r.field, r.stored, r.derived) for r in rows] == [
        ("orders", order.id, "ordered_date", "-", "set")
    ]


def test_the_check_follows_the_reconcilers_set(monkeypatch: pytest.MonkeyPatch) -> None:
    assert checked_aggregates() == lifecycle_reconciler.RECONCILED_AGGREGATES
    enabled = frozenset({_A.ORDER_ITEMS, _A.ORDERS})
    monkeypatch.setattr(lifecycle_reconciler, "RECONCILED_AGGREGATES", enabled)

    assert checked_aggregates() == enabled
