"""
The dashboard summary and the Todo sources against what the browser used to
compute from the whole lists. Each test seeds lots, demands of every kind and
orders in many states, reads every page of the list endpoints the dashboard
and the Todo page used to read, computes the old answer from them the way the
page did, and compares it with the new endpoint.

The rows are stored with the status each case needs, consistent with their
facts or not, because both reads only look at the stored status.
"""

from collections import Counter
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
    MadeItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_extra_cost_model import (
    OrderExtraCostOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.platform.const import API_WEB
from src.modules.platform.const import SERVER_DEFAULT_TIMEZONE
from tests.integration._tenant_day import tenant_today
from tests.integration._terminal_helpers import seed_production
from tests.integration.repository_reads._graph import Graph

pytestmark = pytest.mark.usefixtures("allow_lifecycle_drift")

ZONE = ZoneInfo(SERVER_DEFAULT_TIMEZONE)
# What the Todo page lists: due today, overdue, or within a week of today.
WEEK_AHEAD_DAYS = 7
SPEND_WINDOW_DAYS = 30
DEMAND_STATUSES = ("open", "allocated", "ordered", "fulfilled", "canceled")


def _at_noon(day: date) -> datetime:
    return datetime.combine(day, time(12), tzinfo=ZONE).astimezone(UTC)


class _Seed:
    """Rows of every kind the two reads look at, linked to one fully seeded
    graph so the list endpoints can map them."""

    def __init__(self, db: AsyncSession, graph: Graph) -> None:
        self.db = db
        self.graph = graph
        self.today = tenant_today()
        self._n = 0

    def _next(self) -> int:
        self._n += 1
        return self._n

    async def _add[T](self, row: T) -> T:
        self.db.add(row)
        await self.db.flush()
        return row

    async def lot(self, status: str, **values: Any) -> int:
        made_item = await self.graph.made_item()
        project = await self.graph.project()
        row = await self._add(
            ProductionLotOrmModel(
                created=_at_noon(self.today),
                lot_number=f"LT-{self._next()}",
                quantity=5.0,
                status=status,
                priority=values.pop("priority", "normal"),
                creator_id=self.graph.uid,
                made_item_id=made_item.id,
                project_id=project.id,
                **values,
            )
        )
        return row.id

    def _demand_fields(self, status: str, desired: date | None) -> dict[str, Any]:
        return {
            "created": self.today,
            "status": status,
            "quantity": 2.0,
            "unit": "pcs",
            "creator_id": self.graph.uid,
            "desired_delivery_date": desired,
        }

    async def bought_demand(self, status: str, desired: date | None = None) -> int:
        item = await self.graph.bought_item()
        project = await self.graph.project()
        row = await self._add(
            BoughtItemDemandItemOrmModel(
                item_id=item.id, project_id=project.id, **self._demand_fields(status, desired)
            )
        )
        return row.id

    async def made_demand(self, status: str, desired: date | None = None) -> int:
        item = await self.graph.made_item()
        project = await self.graph.project()
        row = await self._add(
            MadeItemDemandItemOrmModel(
                made_item_id=item.id, project_id=project.id, **self._demand_fields(status, desired)
            )
        )
        return row.id

    async def source_demand(self, status: str, desired: date | None = None) -> int:
        item = await self.graph.source_item()
        project = await self.graph.project()
        # A lot has one raw-material demand, so each demand gets its own.
        lot_id = await self.lot("planned")
        row = await self._add(
            SourceItemDemandItemOrmModel(
                source_item_id=item.id,
                lot_id=lot_id,
                project_id=project.id,
                **self._demand_fields(status, desired),
            )
        )
        return row.id

    async def order(self, status: str, ordered_date: datetime | None = None) -> int:
        supplier = await self.graph.supplier()
        row = await self._add(
            OrderOrmModel(
                order_number=f"OT-{self._next()}",
                created=_at_noon(self.today),
                status=status,
                ordered_date=ordered_date,
                creator_id=self.graph.uid,
                supplier_id=supplier.id,
            )
        )
        return row.id

    async def line(self, order_id: int, status: str, **values: Any) -> int:
        item = await self.graph.bought_item()
        supplier = await self.graph.supplier()
        row = await self._add(
            OrderItemOrmModel(
                created=_at_noon(self.today),
                status=status,
                quantity=values.pop("quantity", 10.0),
                quantity_delivered=values.pop("quantity_delivered", 0.0),
                unit="pcs",
                creator_id=self.graph.uid,
                order_id=order_id,
                supplier_id=supplier.id,
                project_id=values.pop("project_id", None) or (await self.graph.project()).id,
                line_type="BOUGHT",
                bought_item_id=item.id,
                position=self._next(),
                **values,
            )
        )
        return row.id

    async def extra_cost(self, order_id: int, kind: str, amount: int) -> None:
        await self._add(
            OrderExtraCostOrmModel(order_id=order_id, kind=kind, amount=amount, position=0)
        )


@pytest.fixture
async def seed(db: AsyncSession) -> _Seed:
    # The lot list reads the production settings for its lead days.
    await seed_production(db)
    return _Seed(db, await Graph.seed(db))


async def _all_pages(client: httpx.AsyncClient, path: str, **params: Any) -> list[dict[str, Any]]:
    """Every row of a list endpoint, page by page, as the browser read them."""
    rows: list[dict[str, Any]] = []
    while True:
        response = await client.get(
            f"{API_WEB}{path}", params={**params, "skip": len(rows), "limit": 500}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        rows.extend(body["items"])
        if len(body["items"]) < 500 or len(rows) >= body["total"]:
            return rows


def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(row["status"] for row in rows))


def _summary_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    return {entry["status"]: entry["count"] for entry in entries}


async def _seed_mixed(seed: _Seed) -> None:
    """Rows in every state the two reads tell apart."""
    today = seed.today
    soon = today + timedelta(days=3)
    late = today - timedelta(days=4)
    far = today + timedelta(days=40)

    for status in ("draft", "partially_planned", "planned", "in_progress"):
        await seed.lot(status, required_delivery_date=far)
    for status in ("on_hold", "completed", "canceled", "scrapped"):
        await seed.lot(status)
    await seed.lot("draft")
    await seed.lot("partially_planned", required_delivery_date=soon)
    await seed.lot("in_progress", source_approval_status="pending")
    await seed.lot("completed", source_approval_status="pending")

    for kind in (seed.bought_demand, seed.made_demand, seed.source_demand):
        for status in DEMAND_STATUSES:
            await kind(status, late)
        await kind("open")
        await kind("open", soon)
        await kind("open", far)

    in_window = _at_noon(today - timedelta(days=2))
    priced = await seed.order("ordered", in_window)
    await seed.line(priced, "ordered", price=1250, quantity=3.0, expected_delivery_date=far)
    await seed.line(priced, "canceled", price=999, quantity=1.0, canceled_at=in_window)
    await seed.extra_cost(priced, "shipping", 700)
    await seed.extra_cost(priced, "discount", 200)
    costs_only = await seed.order("ordered", _at_noon(today))
    await seed.extra_cost(costs_only, "shipping", 300)
    unpriced = await seed.order("ordered", _at_noon(today - timedelta(days=SPEND_WINDOW_DAYS - 1)))
    await seed.line(unpriced, "ordered", expected_delivery_date=far)
    too_old = await seed.order("delivered", _at_noon(today - timedelta(days=SPEND_WINDOW_DAYS)))
    await seed.line(too_old, "delivered", price=5000, quantity=1.0, quantity_delivered=1.0)

    await seed.order("draft")
    await seed.order("requested")
    pickup = await seed.order("ordered", in_window)
    await seed.line(pickup, "ordered", ready_for_pickup_date=_at_noon(today))
    pickup_later = await seed.order("ordered", in_window)
    await seed.line(pickup_later, "ordered", expected_pickup_date=far)
    partial = await seed.order("partially_delivered", in_window)
    await seed.line(partial, "partially_delivered", quantity_delivered=4.0)
    overdue = await seed.order("ordered", in_window)
    await seed.line(overdue, "ordered", expected_delivery_date=late)
    done = await seed.order("delivered", in_window)
    await seed.line(done, "delivered", quantity_delivered=10.0, expected_delivery_date=late)

    await seed.db.commit()


def _local_day(instant: str) -> date:
    return datetime.fromisoformat(instant).astimezone(ZONE).date()


def _within_week(day: date | None, today: date) -> bool:
    """bucketFor in buildTodoTasks.ts: a dated task is listed when it is
    overdue, due today or due within the week ahead."""
    return day is None or day <= today + timedelta(days=WEEK_AHEAD_DAYS)


def _order_gives_task(order: dict[str, Any], today: date) -> bool:
    """The order rules of buildTodoTasks.ts."""
    if order["status"] in ("draft", "requested", "partially_ordered"):
        return True
    for line in order["items"]:
        if line["status"] in ("delivered", "canceled"):
            continue
        if line["ready_for_pickup_date"]:
            if _within_week(_local_day(line["ready_for_pickup_date"]), today):
                return True
            continue
        if line["expected_pickup_date"]:
            if _within_week(date.fromisoformat(line["expected_pickup_date"]), today):
                return True
            continue
        if 0 < line["quantity_delivered"] < line["quantity"]:
            return True
        expected = line["expected_delivery_date"]
        if expected and date.fromisoformat(expected) < today:
            return True
    return False


def _demand_gives_task(demand: dict[str, Any], today: date) -> bool:
    desired = demand["desired_delivery_date"]
    return demand["status"] == "open" and _within_week(
        date.fromisoformat(desired) if desired else None, today
    )


def _lot_gives_task(lot: dict[str, Any], today: date) -> bool:
    open_lot = lot["status"] not in ("completed", "canceled")
    if lot["source_approval_status"] == "pending" and open_lot:
        return True
    if lot["status"] == "on_hold":
        return True
    if lot["status"] not in ("draft", "partially_planned"):
        return False
    due = lot["required_delivery_date"]
    return _within_week(date.fromisoformat(due) if due else None, today)


def _without_actions(value: Any) -> Any:
    """A row with the lifecycle actions, offered and blocked, left out at
    every level, since only the list endpoints fill them and the Todo page
    reads none."""
    if isinstance(value, dict):
        return {
            k: _without_actions(v)
            for k, v in value.items()
            if k not in ("actions", "blocked_actions")
        }
    if isinstance(value, list):
        return [_without_actions(v) for v in value]
    return value


async def test_the_dashboard_summary_matches_the_counts_taken_over_the_whole_lists(
    seed: _Seed, auth_client: Any
) -> None:
    await _seed_mixed(seed)
    client = await auth_client(username="viewer", email="viewer@example.com")
    today = seed.today
    window_from = today - timedelta(days=SPEND_WINDOW_DAYS - 1)

    lots = await _all_pages(client, "/production-lots/")
    bought = await _all_pages(client, "/bought-items-demands/")
    made = await _all_pages(client, "/made-items-demands/")
    source = await _all_pages(client, "/source-item-demands/")
    recent_orders = await _all_pages(
        client,
        "/orders/",
        ordered_from=window_from.isoformat(),
        ordered_to=today.isoformat(),
    )

    response = await client.get(f"{API_WEB}/dashboard/summary")
    assert response.status_code == 200, response.text
    summary = response.json()

    assert _summary_counts(summary["lots"]) == _counts(lots)
    assert _summary_counts(summary["bought_demands"]) == _counts(bought)
    assert _summary_counts(summary["made_demands"]) == _counts(made)
    assert _summary_counts(summary["source_demands"]) == _counts(source)

    spend = summary["spend"]
    by_day: Counter[date] = Counter()
    for order in recent_orders:
        by_day[_local_day(order["ordered_date"])] += order["net_total"] or 0
    assert spend["window_from"] == window_from.isoformat()
    assert spend["window_to"] == today.isoformat()
    assert spend["order_count"] == len(recent_orders)
    assert spend["net_total"] == sum((order["net_total"] or 0) for order in recent_orders)
    assert [(d["day"], d["net_total"]) for d in spend["days"]] == [
        ((window_from + timedelta(days=i)).isoformat(), by_day[window_from + timedelta(days=i)])
        for i in range(SPEND_WINDOW_DAYS)
    ]
    # The seed puts real money into the window, so the comparison is not
    # one of zeros: 3 x 12.50 + 7.00 - 2.00 on one order, 3.00 on another.
    assert spend["net_total"] == 3750 + 700 - 200 + 300


async def test_the_todo_sources_hold_every_row_that_gives_a_task_and_no_finished_work(
    seed: _Seed, auth_client: Any
) -> None:
    await _seed_mixed(seed)
    client = await auth_client(username="viewer", email="viewer@example.com")
    today = seed.today

    lists = {
        "orders": await _all_pages(client, "/orders/"),
        "bought_demands": await _all_pages(client, "/bought-items-demands/"),
        "made_demands": await _all_pages(client, "/made-items-demands/"),
        "source_demands": await _all_pages(client, "/source-item-demands/"),
        "lots": await _all_pages(client, "/production-lots/"),
    }
    response = await client.get(f"{API_WEB}/todo/sources")
    assert response.status_code == 200, response.text
    sources = response.json()
    assert sources["horizon"] == (today + timedelta(days=8)).isoformat()

    gives_task = {
        "orders": _order_gives_task,
        "bought_demands": _demand_gives_task,
        "made_demands": _demand_gives_task,
        "source_demands": _demand_gives_task,
        "lots": _lot_gives_task,
    }
    finished = {
        "orders": ("delivered", "canceled"),
        "bought_demands": ("fulfilled", "canceled", "allocated", "ordered"),
        "made_demands": ("fulfilled", "canceled", "allocated", "ordered"),
        "source_demands": ("fulfilled", "canceled", "allocated", "ordered"),
        "lots": ("completed", "canceled", "scrapped", "planned", "in_progress"),
    }
    for key, rows in lists.items():
        by_id = {row["id"]: row for row in rows}
        returned = {row["id"]: row for row in sources[key]}
        expected = {row["id"] for row in rows if gives_task[key](row, today)}
        assert expected, key
        assert expected <= returned.keys(), key
        assert returned.keys() < by_id.keys(), key
        # Each row has the shape the list endpoint gives it.
        for row_id, row in returned.items():
            assert _without_actions(row) == _without_actions(by_id[row_id]), (key, row_id)
        # Finished work never reaches the page, apart from the rows whose
        # other facts still give a task.
        assert not [
            row_id
            for row_id, row in returned.items()
            if row["status"] in finished[key] and row_id not in expected
        ], key


async def test_the_todo_sources_leave_out_the_lots_when_asked(
    seed: _Seed, auth_client: Any
) -> None:
    await _seed_mixed(seed)
    client = await auth_client(username="viewer", email="viewer@example.com")

    response = await client.get(f"{API_WEB}/todo/sources", params={"include_lots": "false"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["lots"] == []
    assert body["orders"]
