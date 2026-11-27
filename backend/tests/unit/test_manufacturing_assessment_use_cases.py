"""
Unit tests for the ManufacturingAssessment vertical, a
post-manufacturing assessment prompted at a ProductionOrder's final
completion. A completed order has one active assessment, which a new one
replaces only after a reversal booked later than it. No database, no HTTP.
All dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo
from typing import Any

import pytest

from src.modules.fulfillment.application.dto.production_order_dto import (
    RecordManufacturingAssessmentCommand,
)
from src.modules.fulfillment.application.use_cases.production_order.get_manufacturing_assessment import (
    GetManufacturingAssessment,
)
from src.modules.fulfillment.application.use_cases.production_order.record_manufacturing_assessment import (
    RecordManufacturingAssessment,
)
from src.modules.fulfillment.domain.entities.manufacturing_assessment import ManufacturingAssessment
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.errors import ManufacturingAssessmentAlreadyExistsError
from src.modules.fulfillment.domain.errors import ManufacturingAssessmentNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.domain.value_objects.production_status import ComplexityClass
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.services import clock as clock_module
from tests import factories

# ── Helpers ───────────────────────────────────────────────────────────


def make_user(*, permissions: list[str] | None = None, **overrides: Any) -> User:
    """A user who may write production orders unless the test passes other permissions."""
    if permissions is None:
        permissions = [Permission.WRITE_PRODUCTION_ORDERS]
    return factories.make_user(permissions=permissions, **overrides)


def make_order(
    id: int = 1,
    status: ProductionOrderStatus = ProductionOrderStatus.COMPLETED,
) -> ProductionOrder:
    return ProductionOrder(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        production_order_number=f"PO-{id:04d}",
        status=status,
        priority=UrgencyClass.NORMAL,
        pinned=False,
        queue_sequence=1,
        quantity=10.0,
        quantity_completed=10.0,
        estimated_duration_minutes=30,
        note=None,
        planned_start=None,
        planned_end=None,
        not_before=None,
        actual_start=None,
        actual_end=None,
        creator_id=1,
        machine_id=1,
        lot_position_id=1,
    )


def make_command(
    actual_minutes_per_piece: float = 5,
    actual_setup_minutes: int | None = 15,
    complexity: str = ComplexityClass.NORMAL.value,
    note: str | None = None,
) -> RecordManufacturingAssessmentCommand:
    return RecordManufacturingAssessmentCommand(
        actual_minutes_per_piece=actual_minutes_per_piece,
        actual_setup_minutes=actual_setup_minutes,
        complexity=complexity,
        note=note,
    )


# ── Fakes ────────────────────────────────────────────────────────────


class FakeProductionOrderRepository:
    def __init__(self, orders: list[ProductionOrder] | None = None) -> None:
        self._orders: dict[int, ProductionOrder] = {o.id: o for o in (orders or [])}

    async def get_by_id(self, id: int) -> ProductionOrder | None:
        return self._orders.get(id)


class FakeManufacturingAssessmentRepository:
    """Keeps every row, superseded ones included, and refuses a second
    active row per order as the partial unique index does."""

    def __init__(self) -> None:
        self.rows: list[ManufacturingAssessment] = []
        self._next_id = 1

    async def get_by_production_order_id(
        self, production_order_id: int
    ) -> ManufacturingAssessment | None:
        return next(
            (
                a
                for a in self.rows
                if a.production_order_id == production_order_id and a.superseded_at is None
            ),
            None,
        )

    async def save(self, assessment: ManufacturingAssessment) -> ManufacturingAssessment:
        if await self.get_by_production_order_id(assessment.production_order_id):
            raise ManufacturingAssessmentAlreadyExistsError("active assessment exists")
        if assessment.id == 0:
            assessment.id = self._next_id
            self._next_id += 1
        self.rows.append(assessment)
        return assessment

    async def mark_superseded(self, assessment_id: int, superseded_at: datetime) -> None:
        for row in self.rows:
            if row.id == assessment_id and row.superseded_at is None:
                row.superseded_at = superseded_at


class FakeEventBus:
    def __init__(self) -> None:
        self.published: list[object] = []

    async def publish(self, event: object) -> None:
        self.published.append(event)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


# ── RecordManufacturingAssessment ───────────────────────────────────────


async def test_record_assessment_requires_write_production_orders() -> None:
    """Recording an assessment takes the same write gate as its sibling
    mutations, not merely an active session."""
    actor = make_user(permissions=[])  # no permissions
    order = make_order(id=1, status=ProductionOrderStatus.COMPLETED)
    use_case = RecordManufacturingAssessment(
        assessment_repo=FakeManufacturingAssessmentRepository(),
        order_repo=FakeProductionOrderRepository([order]),
        event_bus=FakeEventBus(),
        uow=FakeUnitOfWork(),
    )

    with pytest.raises(InsufficientPermissionsError):
        await use_case.execute(actor=actor, production_order_id=1, cmd=make_command())


async def test_record_assessment_on_completed_order_succeeds() -> None:
    actor = make_user()
    order = make_order(id=1, status=ProductionOrderStatus.COMPLETED)
    order_repo = FakeProductionOrderRepository([order])
    assessment_repo = FakeManufacturingAssessmentRepository()
    use_case = RecordManufacturingAssessment(
        assessment_repo=assessment_repo,
        order_repo=order_repo,
        event_bus=FakeEventBus(),
        uow=FakeUnitOfWork(),
    )

    result = await use_case.execute(
        actor=actor,
        production_order_id=1,
        cmd=make_command(
            actual_minutes_per_piece=7,
            actual_setup_minutes=20,
            complexity=ComplexityClass.VERY.value,
            note="Tricky fixture setup.",
        ),
    )

    assert result.production_order_id == 1
    assert result.operator_id == actor.id
    assert result.actual_minutes_per_piece == 7
    assert result.actual_setup_minutes == 20
    assert result.complexity == ComplexityClass.VERY.value
    assert result.note == "Tricky fixture setup."
    assert await assessment_repo.get_by_production_order_id(1) is not None


async def test_record_assessment_rejected_when_order_not_found() -> None:
    actor = make_user()
    order_repo = FakeProductionOrderRepository([])
    use_case = RecordManufacturingAssessment(
        assessment_repo=FakeManufacturingAssessmentRepository(),
        order_repo=order_repo,
        event_bus=FakeEventBus(),
        uow=FakeUnitOfWork(),
    )

    with pytest.raises(ProductionOrderNotFoundError):
        await use_case.execute(actor=actor, production_order_id=99, cmd=make_command())


@pytest.mark.parametrize(
    "status",
    [
        ProductionOrderStatus.QUEUED,
        ProductionOrderStatus.IN_PROGRESS,
        ProductionOrderStatus.PAUSED,
        ProductionOrderStatus.CANCELED,
    ],
)
async def test_record_assessment_rejected_on_non_completed_order(
    status: ProductionOrderStatus,
) -> None:
    actor = make_user()
    order = make_order(id=1, status=status)
    order_repo = FakeProductionOrderRepository([order])
    use_case = RecordManufacturingAssessment(
        assessment_repo=FakeManufacturingAssessmentRepository(),
        order_repo=order_repo,
        event_bus=FakeEventBus(),
        uow=FakeUnitOfWork(),
    )

    with pytest.raises(ProductionOrderInvalidStatusTransitionError):
        await use_case.execute(actor=actor, production_order_id=1, cmd=make_command())


async def test_record_assessment_rejected_when_already_exists() -> None:
    actor = make_user()
    order = make_order(id=1, status=ProductionOrderStatus.COMPLETED)
    order_repo = FakeProductionOrderRepository([order])
    assessment_repo = FakeManufacturingAssessmentRepository()
    use_case = RecordManufacturingAssessment(
        assessment_repo=assessment_repo,
        order_repo=order_repo,
        event_bus=FakeEventBus(),
        uow=FakeUnitOfWork(),
    )
    await use_case.execute(actor=actor, production_order_id=1, cmd=make_command())

    with pytest.raises(ManufacturingAssessmentAlreadyExistsError):
        await use_case.execute(actor=actor, production_order_id=1, cmd=make_command())


# ── GetManufacturingAssessment ──────────────────────────────────────────


async def test_get_assessment_returns_recorded_assessment() -> None:
    actor = make_user()
    order = make_order(id=1, status=ProductionOrderStatus.COMPLETED)
    order_repo = FakeProductionOrderRepository([order])
    assessment_repo = FakeManufacturingAssessmentRepository()
    record_use_case = RecordManufacturingAssessment(
        assessment_repo=assessment_repo,
        order_repo=order_repo,
        event_bus=FakeEventBus(),
        uow=FakeUnitOfWork(),
    )
    await record_use_case.execute(actor=actor, production_order_id=1, cmd=make_command())

    get_use_case = GetManufacturingAssessment(assessment_repo=assessment_repo)
    result = await get_use_case.execute(production_order_id=1)

    assert result.production_order_id == 1
    assert result.operator_id == actor.id


async def test_get_assessment_raises_not_found_when_none_recorded() -> None:
    get_use_case = GetManufacturingAssessment(
        assessment_repo=FakeManufacturingAssessmentRepository()
    )

    with pytest.raises(ManufacturingAssessmentNotFoundError):
        await get_use_case.execute(production_order_id=1)


# ── Replacing the assessment after a reversal ───────────────────────────


def _completion(
    id: int, created: datetime, *, reverses: int | None = None
) -> ProductionOrderCompletion:
    """A completion of the whole order, or the reversal of completion
    `reverses` when it is set."""
    quantity = -10.0 if reverses is not None else 10.0
    return ProductionOrderCompletion(
        id=id,
        production_order_id=1,
        quantity=quantity,
        quantity_accepted=quantity,
        quantity_rejected=0.0,
        completion_date=created.date(),
        note=None,
        operator_id=1,
        recorded_by_id=1,
        created=created,
        reverses_completion_id=reverses,
    )


_START = datetime(2026, 3, 2, 8, 0, tzinfo=UTC)


class _Clock(datetime):
    """Stands in for the datetime class of the clock module, so every
    now_utc() call returns the instant the test set last."""

    current = _START

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> datetime:
        return cls.current


class _CompletedOrder:
    """Completed order #1, completed at 08:00. Each assessment is recorded
    an hour after the last booking, and a reversal and the completion after
    it are booked half an hour after the last assessment."""

    @pytest.fixture(autouse=True)
    def _clock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_Clock, "current", _START)
        monkeypatch.setattr(clock_module, "datetime", _Clock)

    def setup_method(self) -> None:
        self.actor = make_user()
        self.order = make_order(id=1, status=ProductionOrderStatus.COMPLETED)
        self.order.completions = [_completion(1, _START)]
        self.assessments = FakeManufacturingAssessmentRepository()
        self.use_case = RecordManufacturingAssessment(
            assessment_repo=self.assessments,
            order_repo=FakeProductionOrderRepository([self.order]),
            event_bus=FakeEventBus(),
            uow=FakeUnitOfWork(),
        )

    async def record(self, minutes: float) -> None:
        _Clock.current += timedelta(hours=1)
        await self.use_case.execute(
            actor=self.actor, production_order_id=1, cmd=make_command(minutes)
        )

    def reverse_and_complete_again(self) -> None:
        """A reversal of the last completion and a new completion, both
        booked after every assessment so far."""
        _Clock.current += timedelta(minutes=30)
        last = self.order.completions[-1].id
        self.order.completions += [
            _completion(last + 1, _Clock.current, reverses=last),
            _completion(last + 2, _Clock.current + timedelta(minutes=1)),
        ]

    def active(self) -> list[float]:
        return [
            a.actual_minutes_per_piece for a in self.assessments.rows if a.superseded_at is None
        ]


class TestReplaceAfterReversal(_CompletedOrder):
    async def test_a_reversal_after_the_assessment_lets_the_next_one_replace_it(self) -> None:
        await self.record(5)
        self.reverse_and_complete_again()

        await self.record(6.5)

        [first, second] = self.assessments.rows
        assert first.superseded_at is not None
        assert (second.actual_minutes_per_piece, second.superseded_at) == (6.5, None)
        assert self.active() == [6.5]

    async def test_without_a_later_reversal_a_second_assessment_is_refused(self) -> None:
        # The order's earlier reversal happened before the assessment, so
        # the assessment already describes the final run.
        self.order.completions = [
            _completion(1, _START - timedelta(hours=3)),
            _completion(2, _START - timedelta(hours=2), reverses=1),
            _completion(3, _START - timedelta(hours=1)),
        ]
        await self.record(5)

        with pytest.raises(ManufacturingAssessmentAlreadyExistsError):
            await self.record(6)

        assert self.active() == [5]

    async def test_a_second_reversal_lets_a_third_assessment_replace_the_second(self) -> None:
        await self.record(5)
        self.reverse_and_complete_again()
        await self.record(6)
        self.reverse_and_complete_again()

        await self.record(7.25)

        assert [a.superseded_at is not None for a in self.assessments.rows] == [True, True, False]
        assert self.active() == [7.25]

    async def test_a_replacement_is_recorded_only_once_per_reversal(self) -> None:
        await self.record(5)
        self.reverse_and_complete_again()
        await self.record(6)

        with pytest.raises(ManufacturingAssessmentAlreadyExistsError):
            await self.record(7)

        assert self.active() == [6]


# ── Decimal minutes ─────────────────────────────────────────────────────


@pytest.mark.parametrize("minutes", [0, 0.5, 2.25, 12.1])
def test_minutes_per_piece_take_up_to_two_decimals(minutes: float) -> None:
    assert make_command(minutes).actual_minutes_per_piece == minutes


@pytest.mark.parametrize("minutes", [2.255, -0.5, float("inf")])
def test_minutes_per_piece_outside_two_decimals_are_refused(minutes: float) -> None:
    with pytest.raises(ValueError):
        make_command(minutes)
