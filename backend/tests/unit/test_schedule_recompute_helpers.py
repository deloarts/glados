"""
Coverage for src/modules/fulfillment/application/services/schedule_recompute_helpers.py.
Every early return here is a "nothing downstream to recompute" guard, and each
one silently doing the wrong thing (recomputing nothing when it should,
or crashing on a missing row) is exactly the kind of bug that only shows
up as a stale schedule board, so they're worth pinning individually.

recompute_downstream_position_machines cascades to every position AFTER
the changed one (not just sequence+1). See its docstring for why:
_context.resolve_predecessor_ready_at walks the whole transitive chain of
earlier positions, so a date change on position 1 can move position 4's
earliest_start as directly as position 2's, and only recomputing
sequence+1 would leave later positions stale.

A recompute is always a single global
RecomputeMachineSchedule.execute_all() walk: which machine(s) a later
position's order happens to sit on does not matter, only whether at least
one live (non-terminal) later order exists at all. So every test below
asserts a call COUNT (0 or 1), not which machines are involved.
"""

from dataclasses import dataclass
from dataclasses import field

from src.modules.fulfillment.application.services.schedule_recompute_helpers import (
    recompute_downstream_position_machines,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus

# ── Fakes ─────────────────────────────────────────────────────────────


@dataclass
class _FakePosition:
    id: int
    lot_id: int
    sequence: int


@dataclass
class _FakeLot:
    id: int
    positions: list[_FakePosition]


@dataclass
class _FakeOrder:
    machine_id: int | None
    lot_position_id: int
    status: str = field(default=ProductionOrderStatus.QUEUED.value)


class _FakeLotRepo:
    def __init__(self, position: _FakePosition | None, lot: _FakeLot | None):
        self._position = position
        self._lot = lot

    async def get_position_by_id(self, position_id: int) -> _FakePosition | None:
        return self._position

    async def get_positions_by_ids(self, position_ids: list[int]) -> list:
        positions = [await self.get_position_by_id(i) for i in position_ids]
        return [p for p in positions if p is not None]

    async def get_by_id(self, lot_id: int) -> _FakeLot | None:
        return self._lot

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]


class _FakeOrderRepo:
    def __init__(self, orders: list[_FakeOrder] | None = None):
        self._orders = orders or []
        self.queried_position_ids: list[int] | None = None

    async def get_by_lot_position_ids(self, lot_position_ids: list[int]) -> list[_FakeOrder]:
        self.queried_position_ids = list(lot_position_ids)
        return [o for o in self._orders if o.lot_position_id in lot_position_ids]


class _SpyRecompute:
    def __init__(self) -> None:
        self.calls: int = 0

    async def execute_all(self, response_time_days=None, settings=None) -> None:
        self.calls += 1


async def _run(lot_repo, order_repo, recompute, position_id: int = 1) -> None:
    await recompute_downstream_position_machines(position_id, lot_repo, order_repo, recompute)  # type: ignore[arg-type]


# ── Tests ─────────────────────────────────────────────────────────────


class TestRecomputeDownstreamPositionMachines:
    async def test_recomputes_once_when_a_downstream_position_has_live_orders(self):
        pos1 = _FakePosition(id=1, lot_id=10, sequence=1)
        pos2 = _FakePosition(id=2, lot_id=10, sequence=2)
        lot = _FakeLot(id=10, positions=[pos1, pos2])
        order_repo = _FakeOrderRepo(
            [
                _FakeOrder(machine_id=5, lot_position_id=2),
                _FakeOrder(machine_id=6, lot_position_id=2),
            ]
        )
        recompute = _SpyRecompute()

        await _run(_FakeLotRepo(pos1, lot), order_repo, recompute)

        assert order_repo.queried_position_ids == [2]
        assert recompute.calls == 1

    async def test_several_downstream_orders_still_trigger_exactly_one_recompute(self):
        """Two (or more) live production orders downstream, whether on the
        same machine or different ones, trigger ONE global recompute, not
        one per order or per machine: execute_all() always re-walks
        everything in a single pass."""
        pos1 = _FakePosition(id=1, lot_id=10, sequence=1)
        pos2 = _FakePosition(id=2, lot_id=10, sequence=2)
        lot = _FakeLot(id=10, positions=[pos1, pos2])
        order_repo = _FakeOrderRepo(
            [
                _FakeOrder(machine_id=5, lot_position_id=2),
                _FakeOrder(machine_id=5, lot_position_id=2),
            ]
        )
        recompute = _SpyRecompute()

        await _run(_FakeLotRepo(pos1, lot), order_repo, recompute)

        assert recompute.calls == 1

    async def test_does_nothing_when_the_position_does_not_exist(self):
        recompute = _SpyRecompute()
        order_repo = _FakeOrderRepo()

        await _run(_FakeLotRepo(None, None), order_repo, recompute)

        assert recompute.calls == 0
        assert order_repo.queried_position_ids is None

    async def test_does_nothing_when_the_lot_does_not_exist(self):
        pos1 = _FakePosition(id=1, lot_id=10, sequence=1)
        recompute = _SpyRecompute()
        order_repo = _FakeOrderRepo()

        await _run(_FakeLotRepo(pos1, None), order_repo, recompute)

        assert recompute.calls == 0
        assert order_repo.queried_position_ids is None

    async def test_does_nothing_when_the_position_is_the_last_in_the_lot(self):
        """No later positions exist, nothing downstream to update."""
        pos1 = _FakePosition(id=1, lot_id=10, sequence=1)
        lot = _FakeLot(id=10, positions=[pos1])
        recompute = _SpyRecompute()
        order_repo = _FakeOrderRepo()

        await _run(_FakeLotRepo(pos1, lot), order_repo, recompute)

        assert recompute.calls == 0
        assert order_repo.queried_position_ids is None

    async def test_does_nothing_when_the_downstream_positions_have_no_orders(self):
        pos1 = _FakePosition(id=1, lot_id=10, sequence=1)
        pos2 = _FakePosition(id=2, lot_id=10, sequence=2)
        lot = _FakeLot(id=10, positions=[pos1, pos2])
        order_repo = _FakeOrderRepo([])
        recompute = _SpyRecompute()

        await _run(_FakeLotRepo(pos1, lot), order_repo, recompute)

        assert order_repo.queried_position_ids == [2]
        assert recompute.calls == 0

    async def test_cascades_to_every_later_position_not_just_the_immediate_successor(self):
        """A 4-position lot: a live order on position 2, 3 OR 4 (including
        the None/manual-QA bucket) must trigger a recompute: the chain
        floor is transitive, so any later position may depend on the
        changed one, not just the one right after it. Still exactly one
        execute_all() call, regardless of how many later positions/orders
        qualify."""
        pos1 = _FakePosition(id=1, lot_id=10, sequence=1)
        pos2 = _FakePosition(id=2, lot_id=10, sequence=2)
        pos3 = _FakePosition(id=3, lot_id=10, sequence=3)
        pos4 = _FakePosition(id=4, lot_id=10, sequence=4)
        lot = _FakeLot(id=10, positions=[pos1, pos2, pos3, pos4])
        order_repo = _FakeOrderRepo(
            [
                _FakeOrder(machine_id=5, lot_position_id=2),
                _FakeOrder(machine_id=6, lot_position_id=3),
                _FakeOrder(machine_id=6, lot_position_id=4),
                # QA/manual step, no machine assigned.
                _FakeOrder(machine_id=None, lot_position_id=4),
            ]
        )
        recompute = _SpyRecompute()

        await _run(_FakeLotRepo(pos1, lot), order_repo, recompute)

        assert order_repo.queried_position_ids is not None
        assert sorted(order_repo.queried_position_ids) == [2, 3, 4]
        assert recompute.calls == 1

    async def test_no_later_live_orders_means_no_call_even_with_terminal_ones_present(self):
        """Every later-position order is COMPLETED or CANCELED, nothing
        left to move, so no recompute is warranted at all (the "are there
        later live orders?" gate this helper's docstring describes)."""
        pos1 = _FakePosition(id=1, lot_id=10, sequence=1)
        pos2 = _FakePosition(id=2, lot_id=10, sequence=2)
        lot = _FakeLot(id=10, positions=[pos1, pos2])
        order_repo = _FakeOrderRepo(
            [
                _FakeOrder(
                    machine_id=5,
                    lot_position_id=2,
                    status=ProductionOrderStatus.COMPLETED.value,
                ),
                _FakeOrder(
                    machine_id=6,
                    lot_position_id=2,
                    status=ProductionOrderStatus.CANCELED.value,
                ),
            ]
        )
        recompute = _SpyRecompute()

        await _run(_FakeLotRepo(pos1, lot), order_repo, recompute)

        assert order_repo.queried_position_ids == [2]
        assert recompute.calls == 0

    async def test_terminal_orders_on_later_positions_are_excluded_but_a_live_one_still_recomputes(
        self,
    ):
        """A mix of terminal and live orders downstream: the terminal ones
        (COMPLETED/CANCELED) have nothing left to move, but the one live
        order still warrants exactly one recompute."""
        pos1 = _FakePosition(id=1, lot_id=10, sequence=1)
        pos2 = _FakePosition(id=2, lot_id=10, sequence=2)
        lot = _FakeLot(id=10, positions=[pos1, pos2])
        order_repo = _FakeOrderRepo(
            [
                _FakeOrder(
                    machine_id=5,
                    lot_position_id=2,
                    status=ProductionOrderStatus.COMPLETED.value,
                ),
                _FakeOrder(
                    machine_id=6,
                    lot_position_id=2,
                    status=ProductionOrderStatus.CANCELED.value,
                ),
                _FakeOrder(machine_id=7, lot_position_id=2),
            ]
        )
        recompute = _SpyRecompute()

        await _run(_FakeLotRepo(pos1, lot), order_repo, recompute)

        assert recompute.calls == 1

    async def test_finds_later_positions_regardless_of_position_list_order(self):
        """lot.positions is not guaranteed sorted by sequence."""
        pos1 = _FakePosition(id=1, lot_id=10, sequence=1)
        pos2 = _FakePosition(id=2, lot_id=10, sequence=2)
        lot = _FakeLot(id=10, positions=[pos2, pos1])
        order_repo = _FakeOrderRepo([_FakeOrder(machine_id=5, lot_position_id=2)])
        recompute = _SpyRecompute()

        await _run(_FakeLotRepo(pos1, lot), order_repo, recompute)

        assert order_repo.queried_position_ids == [2]
        assert recompute.calls == 1
