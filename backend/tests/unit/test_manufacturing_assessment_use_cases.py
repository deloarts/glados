"""
Unit tests for the ManufacturingAssessment vertical, a
post-manufacturing assessment prompted at a ProductionOrder's final
completion. One per completed order, create + read only. No database,
no HTTP. All dependencies replaced with in-memory fakes.
"""

from datetime import date
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
    actual_minutes_per_piece: int = 5,
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
    def __init__(self) -> None:
        self._by_order: dict[int, ManufacturingAssessment] = {}
        self._next_id = 1

    async def get_by_production_order_id(
        self, production_order_id: int
    ) -> ManufacturingAssessment | None:
        return self._by_order.get(production_order_id)

    async def save(self, assessment: ManufacturingAssessment) -> ManufacturingAssessment:
        if assessment.id == 0:
            assessment.id = self._next_id
            self._next_id += 1
        self._by_order[assessment.production_order_id] = assessment
        return assessment


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
