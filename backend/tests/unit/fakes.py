"""
Shared in-memory stand-ins for the unit of work and the event bus, the two
outbound ports nearly every use case test needs. A unit test uses these,
through the `fake_uow` and `fake_event_bus` fixtures or by importing the
classes, rather than defining its own copy.

Repository-shaped fakes stay in their test package or test file, because
they carry per-test seed data and are not interchangeable.
tests/unit/test_fakes_contract.py checks these fakes and every other
fakes module against their ports.
"""

from __future__ import annotations

from typing import Any


class FakeUnitOfWork:
    """In-memory IUnitOfWork. Tracks both a flag and a call count for commit
    and rollback, so a test can assert whichever of the two it needs."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.committed = True
        self.commits += 1

    async def rollback(self) -> None:
        self.rolled_back = True
        self.rollbacks += 1


class FakeEventBus:
    """In-memory IEventBus. Records every published event in order; publish
    never raises, matching the port's contract."""

    def __init__(self) -> None:
        self.published: list[Any] = []

    async def publish(self, event: Any) -> None:
        self.published.append(event)


class FakeBoughtItemUsages:
    """IBoughtItemUsages that records the merge steps in the order they ran,
    for use cases whose tests do not look at the other modules' rows."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int]] = []

    async def merge_lot_sources(self, source_id: int, target_id: int) -> None:
        self.calls.append(("lot_sources", source_id, target_id))

    async def merge_order_items(self, source_id: int, target_id: int) -> None:
        self.calls.append(("order_items", source_id, target_id))

    async def merge_demand_items(self, source_id: int, target_id: int) -> None:
        self.calls.append(("demand_items", source_id, target_id))

    async def merge_source_demands(self, source_id: int, target_id: int) -> None:
        self.calls.append(("source_demands", source_id, target_id))

    async def merge_substitutions(self, source_id: int, target_id: int) -> None:
        self.calls.append(("substitutions", source_id, target_id))

    async def merge_references(self, source_id: int, target_id: int) -> None:
        self.calls.append(("references", source_id, target_id))


class FakeMadeItemUsages:
    """IMadeItemUsages that records the merges it was asked for."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    async def merge_lots_and_demands(self, source_id: int, target_id: int) -> None:
        self.calls.append((source_id, target_id))
