"""
Unit tests for the SourceItemDemandItem "Demand Source Item" pipeline (create,
cancel, update, get). No database, no HTTP. All dependencies replaced with
in-memory fakes. Status is a stored field on the demand itself (kept in
sync elsewhere by the allocation engine, see test_source_item_allocation_use_cases.py),
FakeSourceItemDemandRepository here is a plain in-memory store, mirroring the
real repository's shape.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from types import SimpleNamespace

import pytest

from src.modules.fulfillment.application.dto.source_item_demand_dto import (
    CreateSourceItemDemandCommand,
)
from src.modules.fulfillment.application.dto.source_item_demand_dto import (
    UpdateSourceItemDemandCommand,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.cancel_source_item_demand import (
    CancelSourceItemDemand,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.create_source_item_demand import (
    CreateSourceItemDemand,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.get_source_item_demand import (
    GetSourceItemDemand,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.get_source_item_demand import (
    GetSourceItemDemands,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.update_source_item_demand import (
    UpdateSourceItemDemand,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.update_source_item_demand_status import (
    UpdateSourceItemDemandStatus,
)
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.errors import LotHasNoMaterialSourceError
from src.modules.fulfillment.domain.errors import LotRawMaterialAlreadyLinkedError
from src.modules.fulfillment.domain.errors import SourceItemDemandAlreadyCanceledError
from src.modules.fulfillment.domain.errors import SourceItemDemandLotChoiceRequiredError
from src.modules.fulfillment.domain.errors import SourceItemDemandNotFoundError
from src.modules.fulfillment.domain.errors import SourceItemRequiresReworkStockError
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    SourceItemDemandFilterDto,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.entities.project import Project
from src.shared_kernel.domain.services.clock import now_utc
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.order._helpers import FakeAllocationRepository
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository

# ── Helpers ───────────────────────────────────────────────────────────


def make_lot(
    id: int = 1,
    made_item_id: int = 1,
    input_demand_id: int | None = None,
    source_bought_item_id: int | None = None,
    source_item_id: int | None = 1,
    source_made_item_id: int | None = None,
) -> ProductionLot:
    return ProductionLot(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        lot_number="LOT-1",
        quantity=5.0,
        status=LotStatus.DRAFT,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=made_item_id,
        project_id=1,
        input_demand_id=input_demand_id,
        source_bought_item_id=source_bought_item_id,
        source_item_id=source_item_id,
        source_made_item_id=source_made_item_id,
    )


def make_project(id: int = 1) -> Project:
    return Project(id=id, created=datetime.now(UTC), project_number="P-0001")


class FakeProductionLotRepository:
    def __init__(self, lots: list[ProductionLot] | None = None) -> None:
        self._lots: dict[int, ProductionLot] = {lot.id: lot for lot in (lots or [])}

    async def get_by_id(self, id: int) -> ProductionLot | None:
        return self._lots.get(id)

    async def get_by_id_for_update(self, id: int) -> ProductionLot | None:
        return self._lots.get(id)

    async def save(self, lot: ProductionLot) -> ProductionLot:
        self._lots[lot.id] = lot
        return lot


class FakeProjectRepository:
    def __init__(self, projects: list[Project] | None = None) -> None:
        self._projects: dict[int, Project] = {p.id: p for p in (projects or [])}

    async def lock_for_update(self, id: int) -> None:
        return None

    async def lock_for_share(self, ids: list[int]) -> None:
        return None

    async def get_by_id(self, id: int) -> Project | None:
        return self._projects.get(id)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


class FakeRecomputeSchedule:
    """Recompute scheduler fake: matches unified scheduler contract, see
    tests/unit/production_order/fakes.py's identical class."""

    def __init__(self) -> None:
        self.execute_all_calls: int = 0

    async def execute_all(self, response_time_days=None, settings=None):
        self.execute_all_calls += 1
        return []


class FailingRecomputeSchedule:
    def __init__(self) -> None:
        self.attempts: int = 0

    async def execute_all(self, response_time_days=None, settings=None):
        self.attempts += 1
        raise RuntimeError("scheduling service is down")


class _NoAllocations:
    """The allocations of demands that hold none."""

    async def get_by_demand_item_id(self, demand_item_id: int) -> list:
        return []


class RecordingLotCancel:
    """Stands in for CancelLot: records the lots a demand cancel hands over
    and runs the caller's check against the lot, as CancelLot does once it
    holds the locks."""

    def __init__(self, lot_repo: object | None = None) -> None:
        self._lots = lot_repo
        self.canceled: list[int] = []

    async def execute(self, actor, lot_id, cmd, *, under_lock=None):
        lot = await self._lots.get_by_id(lot_id) if self._lots is not None else None
        if under_lock is not None and lot is not None:
            await under_lock(lot)
        self.canceled.append(lot_id)


class FakeSourceItemDemandRepository:
    """Plain in-memory store: status is a real stored field, not derived,
    so this needs no order-item repository."""

    def __init__(self, demands: list[SourceItemDemandItem] | None = None) -> None:
        self._demands: dict[int, SourceItemDemandItem] = {d.id: d for d in (demands or [])}
        self._next_id = 1

    async def get_by_id(self, id: int) -> SourceItemDemandItem | None:
        return self._demands.get(id)

    async def get_by_id_for_update(self, id: int) -> SourceItemDemandItem | None:
        return self._demands.get(id)

    async def get_multi(self, filters: SourceItemDemandFilterDto):
        items = list(self._demands.values())
        return len(items), items

    async def save(self, demand: SourceItemDemandItem) -> SourceItemDemandItem:
        if demand.id == 0:
            demand.id = self._next_id
            self._next_id += 1
        self._next_id = max(self._next_id, demand.id + 1)
        self._demands[demand.id] = demand
        return demand


def make_demand_item(
    id: int = 0,
    status: SourceItemDemandStatus = SourceItemDemandStatus.OPEN,
    bought_item_id: int | None = None,
    source_item_id: int | None = 1,
    lot_id: int = 1,
) -> SourceItemDemandItem:
    return SourceItemDemandItem(
        id=id,
        created=date(2026, 1, 1),
        changed=date(2026, 1, 1),
        changes=[],
        status=status,
        quantity=5.0,
        unit="pcs",
        items_per_unit=1.0,
        high_priority=False,
        notify_on_delivery=False,
        note=None,
        desired_delivery_date=None,
        creator_id=1,
        bought_item_id=bought_item_id,
        source_item_id=source_item_id,
        lot_id=lot_id,
        project_id=1,
    )


# ── CreateSourceItemDemand ──────────────────────────────────────────────


class TestCreateSourceItemDemand:
    def setup_method(self):
        self.lot = make_lot(source_item_id=1)
        self.lot_repo = FakeProductionLotRepository([self.lot])
        self.demand_repo = FakeSourceItemDemandRepository()
        self.project_repo = FakeProjectRepository([make_project(id=1)])
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])

    def _use_case(self, recompute_schedule=None) -> CreateSourceItemDemand:
        return CreateSourceItemDemand(
            self.lot_repo,
            self.demand_repo,
            self.project_repo,
            recompute_schedule,
            uow=self.uow,
            reconciler=demand_reconciler(source_demands=self.demand_repo),
        )

    def _cmd(self, **kwargs) -> CreateSourceItemDemandCommand:
        defaults = dict(lot_id=1, quantity=5.0)
        defaults.update(kwargs)
        return CreateSourceItemDemandCommand(**defaults)

    async def test_creates_and_links_demand(self):
        result = await self._use_case().execute(self.actor, self._cmd())
        assert result.status == SourceItemDemandStatus.OPEN.value
        assert result.source_item_id == 1
        assert (await self.lot_repo.get_by_id(1)).input_demand_id == result.id
        assert self.uow.committed is True

    async def test_creates_from_bought_item_source(self):
        self.lot.source_item_id = None
        self.lot.source_bought_item_id = 7
        result = await self._use_case().execute(self.actor, self._cmd())
        assert result.bought_item_id == 7
        assert result.source_item_id is None

    async def test_rejects_when_already_linked(self):
        self.lot.input_demand_id = 99
        with pytest.raises(LotRawMaterialAlreadyLinkedError):
            await self._use_case().execute(self.actor, self._cmd())

    async def test_rejects_when_lot_has_no_material_source(self):
        self.lot.source_item_id = None
        with pytest.raises(LotHasNoMaterialSourceError):
            await self._use_case().execute(self.actor, self._cmd())

    async def test_rejects_when_lot_source_is_rework(self):
        self.lot.source_item_id = None
        self.lot.source_made_item_id = 9
        with pytest.raises(SourceItemRequiresReworkStockError):
            await self._use_case().execute(self.actor, self._cmd())

    async def test_recompute_is_called_exactly_once_on_success(self):
        recompute = FakeRecomputeSchedule()
        await self._use_case(recompute).execute(self.actor, self._cmd())
        assert recompute.execute_all_calls == 1

    async def test_recompute_failure_does_not_roll_back_the_commit(self):
        recompute = FailingRecomputeSchedule()
        result = await self._use_case(recompute).execute(self.actor, self._cmd())
        assert recompute.attempts == 1
        assert self.uow.committed is True
        assert (await self.lot_repo.get_by_id(1)).input_demand_id == result.id


# ── CancelSourceItemDemand ──────────────────────────────────────────────


class TestCancelSourceItemDemand:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot = make_lot(input_demand_id=1)
        self.lot_repo = FakeProductionLotRepository([self.lot])
        self.demand_repo = FakeSourceItemDemandRepository()
        self.demand = await self.demand_repo.save(make_demand_item())
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])

    def _cancel(self, recompute=None) -> CancelSourceItemDemand:
        self.lot_cancel = RecordingLotCancel(self.lot_repo)
        return CancelSourceItemDemand(
            self.demand_repo,
            self.lot_repo,
            _NoAllocations(),
            recompute,
            uow=self.uow,
            reconciler=demand_reconciler(source_demands=self.demand_repo),
            cancel_lot=self.lot_cancel,
        )

    async def test_cancels_and_unlinks_lot(self):
        result = await self._cancel().execute(self.actor, self.demand.id, cancel_lot=False)
        assert result.status == SourceItemDemandStatus.CANCELED.value
        assert (await self.lot_repo.get_by_id(1)).input_demand_id is None

    async def test_the_lot_choice_is_required_while_the_lot_waits_on_the_demand(self):
        use_case = self._cancel()
        with pytest.raises(SourceItemDemandLotChoiceRequiredError):
            await use_case.execute(self.actor, self.demand.id)
        assert (await self.demand_repo.get_by_id(self.demand.id)).canceled_at is None
        assert (await self.lot_repo.get_by_id(1)).input_demand_id == self.demand.id
        assert self.uow.committed is False

    async def test_canceling_the_lot_too_hands_the_cancel_to_the_lot(self):
        await self._cancel().execute(self.actor, self.demand.id, cancel_lot=True)
        assert self.lot_cancel.canceled == [1]

    async def test_a_demand_no_lot_waits_on_needs_no_choice(self):
        self.lot.input_demand_id = None
        await self.lot_repo.save(self.lot)
        use_case = self._cancel()
        result = await use_case.execute(self.actor, self.demand.id, cancel_lot=True)
        assert result.status == SourceItemDemandStatus.CANCELED.value
        assert self.lot_cancel.canceled == []

    async def test_already_canceled_rejected(self):
        use_case = self._cancel()
        await use_case.execute(self.actor, self.demand.id, cancel_lot=False)
        with pytest.raises(SourceItemDemandAlreadyCanceledError):
            await use_case.execute(self.actor, self.demand.id, cancel_lot=False)

    async def test_requires_write_lots_when_lot_is_missing(self):
        """Fail-closed: a dangling lot_id must not skip the permission check
        and let any user cancel the demand."""
        dangling = await self.demand_repo.save(make_demand_item(id=0, lot_id=999))
        permissionless = make_user(id=2, permissions=[])
        use_case = self._cancel()
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(permissionless, dangling.id)
        assert (await self.demand_repo.get_by_id(dangling.id)).canceled_at is None

    async def test_the_permission_is_checked_before_the_canceled_state(self):
        """A user without write:lots learns nothing about the demand's state:
        an already canceled demand answers 403 to them, not 409."""
        await self._cancel().execute(self.actor, self.demand.id, cancel_lot=False)
        permissionless = make_user(id=2, permissions=[])

        with pytest.raises(InsufficientPermissionsError):
            await self._cancel().execute(permissionless, self.demand.id)

    async def test_recompute_is_called_exactly_once_on_success(self):
        recompute = FakeRecomputeSchedule()
        use_case = self._cancel(recompute)
        await use_case.execute(self.actor, self.demand.id, cancel_lot=False)
        assert recompute.execute_all_calls == 1

    async def test_recompute_failure_does_not_roll_back_the_commit(self):
        recompute = FailingRecomputeSchedule()
        use_case = self._cancel(recompute)
        result = await use_case.execute(self.actor, self.demand.id, cancel_lot=False)
        assert recompute.attempts == 1
        assert self.uow.committed is True
        assert result.status == SourceItemDemandStatus.CANCELED.value
        assert (await self.lot_repo.get_by_id(1)).input_demand_id is None


# ── UpdateSourceItemDemand ──────────────────────────────────────────────


class TestUpdateSourceItemDemand:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot = make_lot()
        self.lot_repo = FakeProductionLotRepository([self.lot])
        self.demand_repo = FakeSourceItemDemandRepository()
        self.demand = await self.demand_repo.save(make_demand_item())
        self.allocations = FakeSourceItemAllocationRepository()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])

    def _cmd(self, **kwargs) -> UpdateSourceItemDemandCommand:
        defaults = dict(quantity=5.0, unit="pcs")
        defaults.update(kwargs)
        return UpdateSourceItemDemandCommand(**defaults)

    def _use_case(self) -> UpdateSourceItemDemand:
        return UpdateSourceItemDemand(
            self.demand_repo,
            self.lot_repo,
            allocation_repo=self.allocations,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(source_demands=self.demand_repo),
        )

    async def test_updates_while_open(self):
        result = await self._use_case().execute(self.actor, self.demand.id, self._cmd(quantity=8.0))
        assert result.quantity == 8.0

    async def test_an_allocated_demand_takes_a_note_like_the_other_families(self):
        self.demand.status = SourceItemDemandStatus.ALLOCATED
        await self.demand_repo.save(self.demand)

        result = await self._use_case().execute(
            self.actor, self.demand.id, self._cmd(note="Saw cut first")
        )

        assert result.note == "Saw cut first"

    async def test_the_quantity_never_drops_below_what_is_allocated(self):
        self.demand.status = SourceItemDemandStatus.ALLOCATED
        await self.demand_repo.save(self.demand)
        self.allocations.allocations.append(
            SimpleNamespace(demand_item_id=self.demand.id, order_item_id=1, quantity=4.0)
        )

        with pytest.raises(AllocationOverflowError):
            await self._use_case().execute(self.actor, self.demand.id, self._cmd(quantity=3.0))
        result = await self._use_case().execute(self.actor, self.demand.id, self._cmd(quantity=4.0))
        assert result.quantity == 4.0

    async def test_a_canceled_demand_is_not_edited(self):
        self.demand.status = SourceItemDemandStatus.CANCELED
        self.demand.canceled_at = now_utc()
        await self.demand_repo.save(self.demand)

        with pytest.raises(SourceItemDemandAlreadyCanceledError):
            await self._use_case().execute(self.actor, self.demand.id, self._cmd(note="Late"))

    async def test_requires_write_lots_when_lot_is_missing(self):
        """Fail-closed: a dangling lot_id must not skip the permission check
        and let any user edit the demand."""
        dangling = await self.demand_repo.save(make_demand_item(id=0, lot_id=999))
        permissionless = make_user(id=2, permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self._use_case().execute(permissionless, dangling.id, self._cmd(quantity=8.0))
        assert (await self.demand_repo.get_by_id(dangling.id)).quantity == 5.0


# ── UpdateSourceItemDemandStatus ──────────────────────────────────────────


class TestUpdateSourceItemDemandStatus:
    """Behaviour and permission checks of UpdateSourceItemDemandStatus."""

    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot = make_lot()
        self.lot_repo = FakeProductionLotRepository([self.lot])
        self.demand_repo = FakeSourceItemDemandRepository()
        self.demand = await self.demand_repo.save(
            make_demand_item(status=SourceItemDemandStatus.ALLOCATED)
        )
        self.actor = make_user(
            permissions=[Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS]
        )

    def _use_case(self) -> UpdateSourceItemDemandStatus:
        uow = FakeUnitOfWork()
        reconciler = demand_reconciler(source_demands=self.demand_repo)
        cancel = CancelSourceItemDemand(
            self.demand_repo,
            self.lot_repo,
            _NoAllocations(),
            uow=uow,
            reconciler=reconciler,
            cancel_lot=RecordingLotCancel(self.lot_repo),
        )
        return UpdateSourceItemDemandStatus(
            self.demand_repo,
            cancel,
            uow=uow,
            reconciler=reconciler,
            allocation_repo=FakeSourceItemAllocationRepository(),
            bought_allocation_repo=FakeAllocationRepository(),
            order_item_repo=FakeOrderItemRepository(),
        )

    async def test_requires_permission(self):
        permissionless = make_user(id=2, permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self._use_case().execute(
                permissionless, self.demand.id, SourceItemDemandStatus.FULFILLED.value
            )
        assert (
            await self.demand_repo.get_by_id(self.demand.id)
        ).status == SourceItemDemandStatus.ALLOCATED.value

    async def test_permitted_actor_can_transition(self):
        result = await self._use_case().execute(
            self.actor, self.demand.id, SourceItemDemandStatus.FULFILLED.value
        )
        assert result.status == SourceItemDemandStatus.FULFILLED.value


# ── GetSourceItemDemand / GetSourceItemDemands ────────────────────────────


class TestGetSourceItemDemand:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.demand_repo = FakeSourceItemDemandRepository()
        self.demand = await self.demand_repo.save(make_demand_item())

    async def test_gets_by_id(self):
        result = await GetSourceItemDemand(self.demand_repo).execute(demand_id=self.demand.id)
        assert result.id == self.demand.id

    async def test_not_found_raises(self):
        with pytest.raises(SourceItemDemandNotFoundError):
            await GetSourceItemDemand(self.demand_repo).execute(demand_id=999)

    async def test_lists_demands(self):
        result = await GetSourceItemDemands(self.demand_repo).execute(SourceItemDemandFilterDto())
        assert result.total == 1
