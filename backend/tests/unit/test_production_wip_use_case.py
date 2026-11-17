"""
Unit tests for the read-only endpoints: the live WIP overview
(GetProductionWip / compute_wip_summary) and the operator dropdown
(GetOperators). No database, no HTTP. All dependencies replaced
with in-memory fakes, self-contained per this codebase's convention.
"""

from datetime import date

from src.modules.fulfillment.application.use_cases.production_order.get_operators import (
    GetOperators,
)
from src.modules.fulfillment.application.use_cases.production_order.get_production_wip import (
    GetProductionWip,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.services.production_wip_service import compute_wip_summary
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    LotFilterDto,
)
from src.modules.platform.domain.entities.user import User
from tests.factories import make_user

# ── Helpers ───────────────────────────────────────────────────────────


def make_position(
    id: int = 1,
    lot_id: int = 1,
    sequence: int = 1,
    kind: LotPositionKind = LotPositionKind.INTERNAL,
    status: LotPositionStatus = LotPositionStatus.PENDING,
    quantity: float = 10.0,
    quantity_completed: float = 0.0,
    supplier_name: str = "",
    production_orders: list[ProductionOrder] | None = None,
) -> LotPosition:
    return LotPosition(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        sequence=sequence,
        kind=kind,
        status=status,
        quantity=quantity,
        quantity_completed=quantity_completed,
        note=None,
        creator_id=1,
        lot_id=lot_id,
        supplier_name=supplier_name,
        production_orders=production_orders if production_orders is not None else [],
    )


def make_production_order(
    id: int = 1,
    machine_internal_name: str = "Mill 1",
    lot_position_id: int = 1,
) -> ProductionOrder:
    return ProductionOrder(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        production_order_number=f"PO-{id:04d}",
        status=ProductionOrderStatus.QUEUED,
        priority=UrgencyClass.NORMAL,
        pinned=False,
        queue_sequence=1,
        quantity=5.0,
        quantity_completed=0.0,
        estimated_duration_minutes=30,
        note=None,
        planned_start=None,
        planned_end=None,
        not_before=None,
        actual_start=None,
        actual_end=None,
        creator_id=1,
        machine_id=1,
        lot_position_id=lot_position_id,
        machine_internal_name=machine_internal_name,
    )


def make_lot(
    id: int = 1,
    status: LotStatus = LotStatus.IN_PROGRESS,
    quantity: float = 10.0,
    positions: list[LotPosition] | None = None,
) -> ProductionLot:
    return ProductionLot(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        lot_number=f"LOT-{id:04d}",
        quantity=quantity,
        status=status,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=None,
        made_item_part_number="MADE-0001",
        made_item_revision="C",
        made_item_article_name="Bracket",
        positions=positions if positions is not None else [],
    )


# ── Fakes ────────────────────────────────────────────────────────────


class FakeProductionLotRepository:
    """Only implements what GetProductionWip needs, get_multi filtered by
    a single status at a time, mirroring the real repo's LotFilterDto
    contract (status is a single value, not a list)."""

    def __init__(self, lots: list[ProductionLot] | None = None) -> None:
        self._lots = lots or []

    async def get_by_id(self, id: int) -> ProductionLot | None:
        return next((lot for lot in self._lots if lot.id == id), None)

    async def get_by_id_for_update(self, id: int) -> ProductionLot | None:
        return next((lot for lot in self._lots if lot.id == id), None)

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[ProductionLot]:
        return [lot for lot in self._lots if lot.id in ids]

    async def get_multi(self, filters: LotFilterDto) -> tuple[int, list[ProductionLot]]:
        matches = [
            lot
            for lot in self._lots
            if (filters.status is None or lot.status == filters.status)
            and (filters.statuses is None or lot.status in filters.statuses)
        ]
        skip = filters.skip or 0
        page = matches[skip : skip + filters.limit] if filters.limit else matches[skip:]
        return len(matches), page

    async def save(self, lot):
        raise NotImplementedError

    async def next_lot_number(self, template):
        raise NotImplementedError

    async def get_steps(self, lot_id):
        raise NotImplementedError

    async def get_step_by_id(self, step_id):
        raise NotImplementedError

    async def save_step(self, step):
        raise NotImplementedError

    async def delete_step(self, step):
        raise NotImplementedError

    async def reorder_steps(self, lot_id, ordered_step_ids):
        raise NotImplementedError

    async def get_positions(self, lot_id):
        raise NotImplementedError

    async def get_position_by_id(self, position_id):
        raise NotImplementedError

    async def get_positions_by_ids(self, position_ids: list[int]) -> list:
        positions = [await self.get_position_by_id(i) for i in position_ids]
        return [p for p in positions if p is not None]

    async def save_position(self, position):
        raise NotImplementedError

    async def delete_position(self, position):
        raise NotImplementedError


class FakeUserRepository:
    def __init__(self, users: list[User] | None = None) -> None:
        self._users = users or []

    async def get_by_id(self, id: int) -> User | None:
        return next((u for u in self._users if u.id == id), None)

    async def get_by_username(self, username: str) -> User | None:
        return next((u for u in self._users if u.username == username), None)

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._users if u.email == email), None)

    async def get_by_rfid(self, rfid: str) -> User | None:
        raise NotImplementedError

    async def get_multi(self, filters):
        matches = [
            u for u in self._users if filters.is_active is None or u.is_active == filters.is_active
        ]
        return len(matches), matches

    async def save(self, user):
        raise NotImplementedError

    async def delete(self, user):
        raise NotImplementedError


# ── compute_wip_summary (pure domain service) ───────────────────────────


def test_wip_summary_two_positions_first_complete_second_partial():
    """10 pcs lot: position 1 (milling) fully completed 10/10, position 2
    (assembly) partially completed 4/10, raw=0, finished=4."""
    pos1 = make_position(id=1, sequence=1, quantity=10.0, quantity_completed=10.0)
    pos2 = make_position(id=2, sequence=2, quantity=10.0, quantity_completed=4.0)
    lot = make_lot(quantity=10.0, positions=[pos2, pos1])  # deliberately out of order

    summary = compute_wip_summary(lot)

    assert summary.raw_count == 0.0
    assert summary.finished_count == 4.0
    assert [s.position_id for s in summary.stages] == [1, 2]  # re-sorted by sequence


def test_wip_summary_raw_waiting_before_first_position():
    """Nothing completed anywhere yet, all 10 pcs are raw/waiting."""
    pos1 = make_position(id=1, sequence=1, quantity=10.0, quantity_completed=0.0)
    lot = make_lot(quantity=10.0, positions=[pos1])

    summary = compute_wip_summary(lot)

    assert summary.raw_count == 10.0
    assert summary.finished_count == 0.0


def test_wip_summary_internal_position_exposes_machine_names():
    po = make_production_order(id=1, machine_internal_name="Mill 1", lot_position_id=1)
    pos1 = make_position(
        id=1,
        sequence=1,
        kind=LotPositionKind.INTERNAL,
        quantity=10.0,
        quantity_completed=3.0,
        production_orders=[po],
    )
    lot = make_lot(quantity=10.0, positions=[pos1])

    summary = compute_wip_summary(lot)

    assert summary.stages[0].machine_names == ["Mill 1"]
    assert summary.stages[0].supplier_name == ""


def test_wip_summary_external_position_exposes_supplier_name():
    pos1 = make_position(
        id=1,
        sequence=1,
        kind=LotPositionKind.EXTERNAL,
        quantity=10.0,
        quantity_completed=0.0,
        supplier_name="Acme Supplier",
    )
    lot = make_lot(quantity=10.0, positions=[pos1])

    summary = compute_wip_summary(lot)

    assert summary.stages[0].supplier_name == "Acme Supplier"
    assert summary.stages[0].machine_names == []


# ── GetProductionWip use case ───────────────────────────────────────────


async def test_get_production_wip_excludes_draft_completed_canceled():
    active_lot = make_lot(id=1, status=LotStatus.IN_PROGRESS)
    draft_lot = make_lot(id=2, status=LotStatus.DRAFT)
    completed_lot = make_lot(id=3, status=LotStatus.COMPLETED)
    canceled_lot = make_lot(id=4, status=LotStatus.CANCELED)
    released_lot = make_lot(id=5, status=LotStatus.PARTIALLY_PLANNED)
    on_hold_lot = make_lot(id=6, status=LotStatus.ON_HOLD)

    repo = FakeProductionLotRepository(
        [active_lot, draft_lot, completed_lot, canceled_lot, released_lot, on_hold_lot]
    )
    use_case = GetProductionWip(lot_repo=repo)

    result = await use_case.execute()

    result_ids = {r.id for r in result}
    assert result_ids == {1, 5, 6}


async def test_get_production_wip_result_shape():
    pos1 = make_position(id=1, sequence=1, quantity=10.0, quantity_completed=10.0)
    pos2 = make_position(id=2, sequence=2, quantity=10.0, quantity_completed=4.0)
    lot = make_lot(id=1, status=LotStatus.IN_PROGRESS, quantity=10.0, positions=[pos1, pos2])
    repo = FakeProductionLotRepository([lot])
    use_case = GetProductionWip(lot_repo=repo)

    [result] = await use_case.execute()

    assert result.lot_number == "LOT-0001"
    assert result.made_item_part_number == "MADE-0001"
    assert result.made_item_revision == "C"
    assert result.raw_count == 0.0
    assert result.finished_count == 4.0
    assert len(result.stages) == 2


# ── GetOperators use case ─────────────────────────────────────────────


async def test_get_operators_excludes_inactive_service_and_shared_accounts():
    personal = make_user(id=1, username="alice")
    inactive = make_user(id=2, username="bob", is_active=False)
    service = make_user(id=3, username="api-key-bot", is_service_account=True)
    shared = make_user(id=4, username="shopfloor", is_shared_account=True)

    repo = FakeUserRepository([personal, inactive, service, shared])
    use_case = GetOperators(user_repo=repo)

    result = await use_case.execute(personal)

    assert [r.username for r in result] == ["alice"]


async def test_get_operators_scopes_shared_account_to_its_members():
    alice = make_user(id=1, username="alice")
    bob = make_user(id=2, username="bob")
    carol = make_user(id=3, username="carol")
    terminal = make_user(
        id=4, username="shopfloor", is_shared_account=True, member_ids=[alice.id, bob.id]
    )

    repo = FakeUserRepository([alice, bob, carol, terminal])
    use_case = GetOperators(user_repo=repo)

    result = await use_case.execute(terminal)

    assert {r.username for r in result} == {"alice", "bob"}


async def test_get_operators_returns_nothing_for_unconfigured_shared_account():
    alice = make_user(id=1, username="alice")
    terminal = make_user(id=2, username="shopfloor", is_shared_account=True, member_ids=[])

    repo = FakeUserRepository([alice, terminal])
    use_case = GetOperators(user_repo=repo)

    result = await use_case.execute(terminal)

    assert result == []
