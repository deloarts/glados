"""
The permission matrix of the three manual demand status use cases (bought,
made and source item demands), which share one rule: a user without
write:demand_items, the creator, another user and a manager, each against
the two statuses a user sets, fulfilled and canceled, and the three the
allocations decide, which nobody sets. A refused change leaves the demand,
the event bus and the unit of work untouched, and for a made demand never
reaches the cancel cascade. No database, no HTTP.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from typing import Any

import pytest

from src.modules.catalogue.domain.events.bought_item_events import DemandItemStatusChanged
from src.modules.catalogue.domain.events.made_item_events import MadeItemDemandItemStatusChanged
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.mappers.made_item_demand_mapper import (
    MadeItemDemandItemMapper,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.cancel_demand_item import (
    CancelDemandItem,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.update_demand_item_status import (
    UpdateDemandItemStatus as UpdateBoughtDemandStatus,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.update_demand_item_status import (
    UpdateDemandItemStatus as UpdateMadeDemandStatus,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.cancel_source_item_demand import (
    CancelSourceItemDemand,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.update_source_item_demand_status import (
    UpdateSourceItemDemandStatus,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.errors import DemandItemAlreadyCanceledError
from src.modules.fulfillment.domain.errors import DemandItemInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import DemandItemOfAnotherUserError
from src.modules.fulfillment.domain.errors import SourceItemDemandAlreadyCanceledError
from src.modules.fulfillment.domain.events.source_item_demand_events import (
    SourceItemDemandStatusChanged,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.order._helpers import FakeAllocationRepository
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.test_source_item_demand_use_cases import RecordingLotCancel

DEMAND_ID = 10
CREATOR_ID = 1
START_STATUS = "allocated"
# Statuses the allocations decide, which no user sets.
DERIVED_TARGETS = ["ordered", "open"]
IRREVERSIBLE_TARGETS = ["fulfilled", "canceled"]
ALL_TARGETS = DERIVED_TARGETS + IRREVERSIBLE_TARGETS


def _user(id: int, permissions: list[str]) -> User:
    return User(
        id=id,
        username=f"user{id}",
        full_name=f"User {id}",
        email=f"user{id}@example.com",
        created=datetime(2026, 1, 1, tzinfo=UTC),
        hashed_password="not-a-real-hash",
        is_active=True,
        is_systemuser=False,
        permissions=permissions,
        language=Language.enGB,
        date_format=DateFormat.ISO,
        start_page=StartPage.DASHBOARD,
        theme_preset=ThemePreset.Aura,
        theme_surface=ThemeSurface.glados,
        theme_primary=ThemePrimary.glados,
        theme_dark_mode=False,
        button_flat_style=False,
        table_gridlines=False,
        table_striped_rows=False,
    )


READ_ONLY = _user(4, [])
CREATOR = _user(CREATOR_ID, [Permission.WRITE_DEMAND_ITEMS])
OTHER_USER = _user(2, [Permission.WRITE_DEMAND_ITEMS])
MANAGER = _user(3, [Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS])


class _DemandRepository:
    """Holds the one demand under test, of any family."""

    def __init__(self, demand: Any) -> None:
        self.demand = demand
        self.saves = 0

    async def get_by_id(self, id: int) -> Any:
        return self.demand if id == self.demand.id else None

    async def save(self, demand: Any) -> Any:
        self.saves += 1
        self.demand = demand
        return demand


class _NoAllocations:
    """The allocations of a demand that holds none."""

    async def get_by_demand_item_id(self, demand_item_id: int) -> list[Any]:
        return []

    async def delete(self, allocation: Any) -> None:
        raise AssertionError("The demand under test holds no allocation.")


class _NoLots:
    """A source demand's lot, unknown to the test."""

    async def get_by_id(self, id: int) -> None:
        return None


class _CancelMadeDemand:
    """Stands in for CancelMadeItemDemand, the cascade the made use case
    hands CANCELED to, and records every call that reaches it."""

    def __init__(self, demands: _DemandRepository) -> None:
        self._demands = demands
        self.calls: list[int] = []

    async def execute_permitted(self, actor: User, demand_id: int) -> Any:
        self.calls.append(demand_id)
        demand = await self._demands.get_by_id(demand_id)
        demand.status = MadeItemDemandStatus.CANCELED
        return MadeItemDemandItemMapper.to_result(demand)


@dataclass
class _Family:
    """One family's status use case, wired to in-memory fakes."""

    demands: _DemandRepository
    bus: FakeEventBus
    uow: FakeUnitOfWork
    status_event: type | None
    execute: Callable[[User, str], Awaitable[Any]]
    cancel: _CancelMadeDemand | None = None

    @property
    def demand(self) -> Any:
        return self.demands.demand

    def assert_untouched(self) -> None:
        assert self.demand.status == START_STATUS
        assert self.demand.changes == []
        assert self.demands.saves == 0
        assert self.bus.published == []
        assert not self.uow.committed
        if self.cancel is not None:
            assert self.cancel.calls == []


def _common_fields() -> dict[str, Any]:
    return {
        "id": DEMAND_ID,
        "created": date(2026, 1, 1),
        "changed": None,
        "changes": [],
        "quantity": 5.0,
        "unit": "pcs",
        "items_per_unit": 1.0,
        "high_priority": False,
        "notify_on_delivery": False,
        "note": None,
        "desired_delivery_date": None,
        "creator_id": CREATOR_ID,
        "project_id": 1,
    }


def _bought() -> _Family:
    demands = _DemandRepository(
        BoughtItemDemandItem(item_id=1, status=BoughtItemDemandStatus.ALLOCATED, **_common_fields())
    )
    bus, uow = FakeEventBus(), FakeUnitOfWork()
    reconciler = demand_reconciler(bought_demands=demands, bus=bus)
    cancel = CancelDemandItem(demands, _NoAllocations(), uow=uow, reconciler=reconciler)
    use_case = UpdateBoughtDemandStatus(
        demands,
        cancel,
        uow=uow,
        reconciler=reconciler,
        allocation_repo=FakeAllocationRepository(),
        source_allocation_repo=FakeSourceItemAllocationRepository(),
        order_item_repo=FakeOrderItemRepository(),
    )
    return _Family(
        demands,
        bus,
        uow,
        DemandItemStatusChanged,
        lambda actor, target: use_case.execute(actor, DEMAND_ID, target),
    )


def _made() -> _Family:
    demands = _DemandRepository(
        MadeItemDemandItem(
            made_item_id=1, status=MadeItemDemandStatus.ALLOCATED, **_common_fields()
        )
    )
    bus, uow = FakeEventBus(), FakeUnitOfWork()
    cancel = _CancelMadeDemand(demands)
    reconciler = demand_reconciler(made_demands=demands, bus=bus)
    use_case = UpdateMadeDemandStatus(demands, cancel, uow=uow, reconciler=reconciler)
    return _Family(
        demands,
        bus,
        uow,
        MadeItemDemandItemStatusChanged,
        lambda actor, target: use_case.execute(actor, DEMAND_ID, target),
        cancel,
    )


def _source() -> _Family:
    demands = _DemandRepository(
        SourceItemDemandItem(
            bought_item_id=None,
            source_item_id=1,
            lot_id=1,
            status=SourceItemDemandStatus.ALLOCATED,
            **_common_fields(),
        )
    )
    bus, uow = FakeEventBus(), FakeUnitOfWork()
    reconciler = demand_reconciler(source_demands=demands, bus=bus)
    cancel = CancelSourceItemDemand(
        demands,
        _NoLots(),
        _NoAllocations(),
        uow=uow,
        reconciler=reconciler,
        cancel_lot=RecordingLotCancel(),
    )
    use_case = UpdateSourceItemDemandStatus(
        demands,
        cancel,
        uow=uow,
        reconciler=reconciler,
        allocation_repo=FakeSourceItemAllocationRepository(),
        bought_allocation_repo=FakeAllocationRepository(),
        order_item_repo=FakeOrderItemRepository(),
    )
    return _Family(
        demands,
        bus,
        uow,
        SourceItemDemandStatusChanged,
        lambda actor, target: use_case.execute(actor, DEMAND_ID, target),
    )


@pytest.fixture(params=[_bought, _made, _source], ids=["bought", "made", "source"])
def family(request: pytest.FixtureRequest) -> _Family:
    builder: Callable[[], _Family] = request.param
    return builder()


@pytest.mark.parametrize("target", ALL_TARGETS)
async def test_demand_status_change_refuses_a_read_only_user(family: _Family, target: str) -> None:
    with pytest.raises(InsufficientPermissionsError) as raised:
        await family.execute(READ_ONLY, target)
    assert raised.type is InsufficientPermissionsError
    family.assert_untouched()


@pytest.mark.parametrize("target", ALL_TARGETS)
async def test_demand_status_change_refuses_another_users_demand(
    family: _Family, target: str
) -> None:
    with pytest.raises(DemandItemOfAnotherUserError):
        await family.execute(OTHER_USER, target)
    family.assert_untouched()


@pytest.mark.parametrize("target", DERIVED_TARGETS)
async def test_demand_status_change_refuses_a_status_the_allocations_decide(
    family: _Family, target: str
) -> None:
    for actor in (CREATOR, MANAGER):
        with pytest.raises(DemandItemInvalidStatusTransitionError, match="cannot be set"):
            await family.execute(actor, target)
    family.assert_untouched()


@pytest.mark.parametrize("target", IRREVERSIBLE_TARGETS)
async def test_demand_status_change_keeps_irreversible_targets_from_the_creator(
    family: _Family, target: str
) -> None:
    with pytest.raises(InsufficientPermissionsError, match="manage:demand_items") as raised:
        await family.execute(CREATOR, target)
    assert raised.type is InsufficientPermissionsError
    family.assert_untouched()


@pytest.mark.parametrize("target", IRREVERSIBLE_TARGETS)
async def test_demand_status_change_lets_a_manager_set_an_irreversible_status(
    family: _Family, target: str
) -> None:
    result = await family.execute(MANAGER, target)

    assert result.status == target
    assert family.demand.status == target
    if family.cancel is not None and target == "canceled":
        # The made cancel cascade is a stand-in here; its own tests cover it.
        return
    assert family.uow.committed
    assert [type(event) for event in family.bus.published] == [family.status_event]


async def test_demand_status_change_refuses_an_unknown_status_from_a_read_only_user(
    family: _Family,
) -> None:
    # The rule runs before the status is parsed, so the answer is a refusal,
    # not a list of the valid statuses.
    with pytest.raises(InsufficientPermissionsError):
        await family.execute(READ_ONLY, "not-a-status")
    family.assert_untouched()


async def test_demand_status_change_refuses_an_unchanged_status_from_a_read_only_user(
    family: _Family,
) -> None:
    with pytest.raises(InsufficientPermissionsError):
        await family.execute(READ_ONLY, START_STATUS)
    family.assert_untouched()


async def test_a_canceled_demand_takes_no_further_intent(family: _Family) -> None:
    # The canceled member of the family's own status enum.
    family.demand.status = type(family.demand.status).CANCELED
    family.demand.canceled_at = datetime(2026, 1, 2, tzinfo=UTC)
    with pytest.raises((DemandItemAlreadyCanceledError, SourceItemDemandAlreadyCanceledError)):
        await family.execute(MANAGER, "fulfilled")
    assert family.demand.status == "canceled"
    assert family.demand.fulfilled_manually_at is None
    assert not family.uow.committed


async def test_made_demand_cancel_reaches_the_cascade_only_for_a_manager() -> None:
    made = _made()
    assert made.cancel is not None

    with pytest.raises(InsufficientPermissionsError):
        await made.execute(CREATOR, "canceled")
    assert made.cancel.calls == []

    await made.execute(MANAGER, "canceled")
    assert made.cancel.calls == [DEMAND_ID]
