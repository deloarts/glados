"""
LifecycleRepair on the fake world. A dry run lists exactly the drift
report's rows and writes and locks nothing. An apply writes them through the
reconciler, as the given actor with the changelog reason "lifecycle repair",
publishes no events, commits page by page, and a second run finds nothing.
Fact anomalies are left for a manual step, and a page that loses a race is
read again and retried.
"""

from datetime import timedelta

import pytest

from src.modules.fulfillment.application.services import lifecycle_repair
from src.modules.fulfillment.application.services.lifecycle_drift import LifecycleDriftReport
from src.modules.fulfillment.application.services.lifecycle_repair import LifecycleRepair
from src.modules.fulfillment.application.services.lifecycle_repair import RepairAction
from src.modules.fulfillment.application.services.lifecycle_repair import RepairReport
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.lifecycle.fake_world import NOW
from tests.unit.lifecycle.fake_world import FakeWorld
from tests.unit.lifecycle.fake_world import actor

_A = LifecycleAggregate
RUN = NOW + timedelta(days=1)
SYSTEM = actor(99, "System")


@pytest.fixture(autouse=True)
def _run_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lifecycle_repair, "now_utc", lambda: RUN)


def _repair(
    world: FakeWorld, uow: FakeUnitOfWork | None = None, **values: object
) -> LifecycleRepair:
    return LifecycleRepair(
        world.repositories,
        uow or FakeUnitOfWork(),
        batch_size=values.pop("batch_size", 200),  # type: ignore[arg-type]
        **values,  # type: ignore[arg-type]
    )


def _found(report: RepairReport) -> set[tuple[str, str, str, str, str]]:
    return {(r.action.value, r.table, r.field, r.stored, r.repaired) for r in report.rows}


def _drifting_world() -> FakeWorld:
    """A lot whose external line arrived in full while every stored status
    still says ordered or pending."""
    world = FakeWorld()
    lot = world.lot(status=LotStatus.DRAFT)
    position = world.position(
        lot, kind=LotPositionKind.UNASSIGNED, status=LotPositionStatus.PENDING
    )
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    world.line(
        order, status=OrderItemStatus.ORDERED, ordered_date=NOW, delivered=10.0, position=position
    )
    return world


class TestDryRun:
    async def test_it_lists_the_drift_reports_rows_and_writes_nothing(self) -> None:
        world = _drifting_world()
        uow = FakeUnitOfWork()

        report = await _repair(world, uow).plan()

        drift = await LifecycleDriftReport(world.repositories).run()
        assert {(r.table, r.field, r.stored) for r in report.rows} == {
            (r.table, r.field, r.stored) for r in drift.rows
        }
        assert {r.action for r in report.rows} == {RepairAction.DERIVED}
        assert ("derived", "lots", "completed_at", "-", RUN.isoformat()) in _found(report)
        assert report.needs_attention and not report.applied
        assert (world.saves, world.lock_log, uow.commits) == ([], [], 0)

    async def test_a_consistent_world_needs_nothing(self) -> None:
        world = FakeWorld()
        world.order(status=OrderStatus.DRAFT)

        report = await _repair(world).plan()

        assert report.rows == []
        assert not report.needs_attention


class TestApply:
    async def test_it_writes_the_derivation_with_a_repair_changelog_line(self) -> None:
        world = _drifting_world()
        uow = FakeUnitOfWork()

        report = await _repair(world, uow).apply(SYSTEM)

        lot = next(iter(world.lots.values()))
        order = next(iter(world.orders.values()))
        assert (lot.status, lot.completed_at) == ("completed", RUN)
        assert (order.status, order.delivery_date) == ("delivered", RUN)
        assert "System" in lot.changes[0]
        assert lot.changes[0].endswith("Status: draft → completed (lifecycle repair).")
        assert {(r.table, r.field) for r in report.rows} >= {
            ("lots", "status"),
            ("orders", "status"),
            ("order_items", "status"),
            ("lot_positions", "kind"),
        }
        assert report.applied and report.left == [] and not report.needs_attention
        assert uow.commits == 2  # the lot page and the order page

    async def test_a_second_run_changes_nothing(self) -> None:
        world = _drifting_world()
        await _repair(world).apply(SYSTEM)
        world.saves.clear()
        world.lock_log.clear()
        uow = FakeUnitOfWork()

        report = await _repair(world, uow).apply(SYSTEM)

        assert (report.rows, report.left) == ([], [])
        assert (world.saves, world.lock_log, uow.commits) == ([], [], 0)

    async def test_it_publishes_no_events(self, monkeypatch: pytest.MonkeyPatch) -> None:
        buses: list[object] = []
        real = lifecycle_repair.LifecycleReconciler

        def capture(repositories, bus, **values):  # type: ignore[no-untyped-def]
            buses.append(bus)
            return real(repositories, bus, **values)

        monkeypatch.setattr(lifecycle_repair, "LifecycleReconciler", capture)
        world = _drifting_world()

        await _repair(world).apply(SYSTEM)

        assert buses and all(isinstance(b, lifecycle_repair._DroppedEvents) for b in buses)
        # Lot timeline rows are still written for the lot's status change.
        assert world.lot_events

    async def test_only_the_chosen_tables_are_started_from(self) -> None:
        world = _drifting_world()
        world.order(status=OrderStatus.ORDERED)  # an order without lines derives draft

        report = await _repair(world).apply(SYSTEM, [_A.ORDERS])

        assert {r.table for r in report.rows} == {"orders"}
        assert next(iter(world.lots.values())).status == "draft"

    async def test_each_page_commits_on_its_own(self) -> None:
        world = FakeWorld()
        for _ in range(3):
            world.order(status=OrderStatus.ORDERED)
        uow = FakeUnitOfWork()

        await _repair(world, uow, batch_size=1).apply(SYSTEM)

        assert uow.commits == 3
        assert {o.status for o in world.orders.values()} == {"draft"}


class TestManualRows:
    async def test_a_fact_anomaly_is_listed_and_left_alone(self) -> None:
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

        plan = await _repair(world).plan()
        report = await _repair(world).apply(SYSTEM)

        assert [(r.action, r.field) for r in plan.rows] == [
            (RepairAction.MANUAL, "quantity_completed")
        ]
        assert plan.needs_attention
        assert report.rows == [] and world.saves == []
        assert [(r.field, r.anomaly) for r in report.left] == [("quantity_completed", True)]
        assert report.needs_attention


class TestRetries:
    async def test_a_page_that_loses_a_race_is_retried(self) -> None:
        world = _drifting_world()
        uow = FakeUnitOfWork()

        def lose() -> None:
            raise TimeoutError("lock timeout")

        world.on_first_lock = lose

        report = await _repair(world, uow, retryable=lambda e: isinstance(e, TimeoutError)).apply(
            SYSTEM
        )

        assert uow.rollbacks == 1
        assert report.left == []
        assert next(iter(world.lots.values())).status == "completed"

    async def test_a_retried_page_is_read_again(self) -> None:
        """While the first attempt waits, a request leaves a second order of
        the page differing; the retry reads the page again and repairs it."""
        world = _drifting_world()
        later = world.order(status=OrderStatus.DRAFT)
        world.line(later, status=OrderItemStatus.ORDERED, ordered_date=NOW)
        world.orders[later.id].status = OrderStatus.ORDERED
        world.orders[later.id].ordered_date = NOW
        uow = FakeUnitOfWork()

        def lose() -> None:
            world.orders[later.id].status = OrderStatus.DRAFT
            raise TimeoutError("lock timeout")

        world.on_first_lock = lose

        report = await _repair(world, uow, retryable=lambda e: isinstance(e, TimeoutError)).apply(
            SYSTEM, [_A.ORDERS]
        )

        assert uow.rollbacks == 1
        assert ("orders", later.id, "status") in {(r.table, r.id, r.field) for r in report.rows}
        assert world.orders[later.id].status == "ordered"
        assert report.left == []

    async def test_any_other_failure_rolls_back_and_raises(self) -> None:
        world = _drifting_world()
        uow = FakeUnitOfWork()

        def fail() -> None:
            raise RuntimeError("broken")

        world.on_first_lock = fail

        with pytest.raises(RuntimeError):
            await _repair(world, uow).apply(SYSTEM)
        assert (uow.rollbacks, uow.commits) == (1, 0)

    async def test_a_page_gives_up_after_three_attempts(self) -> None:
        world = _drifting_world()
        uow = FakeUnitOfWork()
        attempts = 0
        lots = world.repositories.lots
        original = lots.lock_for_update

        async def always_lose(ids: list[int]) -> None:
            nonlocal attempts
            attempts += 1
            raise TimeoutError("lock timeout")

        lots.lock_for_update = always_lose  # type: ignore[method-assign]

        with pytest.raises(TimeoutError):
            await _repair(world, uow, retryable=lambda e: isinstance(e, TimeoutError)).apply(SYSTEM)
        lots.lock_for_update = original  # type: ignore[method-assign]
        assert (attempts, uow.rollbacks, uow.commits) == (3, 3, 0)
