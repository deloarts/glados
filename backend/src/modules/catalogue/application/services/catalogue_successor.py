"""Applies the catalogue status rule
(src/modules/catalogue/domain/policies/catalogue_item_status.py) to one write,
loading what the rule needs to know about the successor the write names:
whether it exists, whether it is archived and which successors follow it.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from typing import Protocol

from src.modules.catalogue.domain.policies.catalogue_item_status import CatalogueStatusChange
from src.modules.catalogue.domain.policies.catalogue_item_status import SuccessorFacts
from src.modules.catalogue.domain.policies.catalogue_item_status import (
    assert_catalogue_status_change,
)
from src.modules.catalogue.domain.policies.catalogue_item_status import successor_to_check


class CatalogueRow(Protocol):
    """A made, bought or source item as far as its successor chain goes."""

    @property
    def id(self) -> int: ...

    @property
    def archived(self) -> bool: ...

    @property
    def successor_item_id(self) -> int | None: ...


async def load_successor_facts(
    get_by_id: Callable[[int], Awaitable[CatalogueRow | None]], successor_id: int
) -> SuccessorFacts | None:
    """The successor as the rule sees it, None when it does not exist. Its
    chain follows the stored successor links until one ends or repeats, so a
    loop that is already stored cannot keep the walk going."""
    first = await get_by_id(successor_id)
    if first is None:
        return None
    chain: list[int] = []
    seen = {first.id}
    next_id = first.successor_item_id
    while next_id is not None and next_id not in seen:
        chain.append(next_id)
        seen.add(next_id)
        row = await get_by_id(next_id)
        next_id = row.successor_item_id if row is not None else None
    return SuccessorFacts(id=first.id, archived=first.archived, chain=tuple(chain))


async def resolve_successor(
    change: CatalogueStatusChange,
    get_by_id: Callable[[int], Awaitable[CatalogueRow | None]],
) -> int | None:
    """Raises when the write leaves status and successor inconsistent, and
    returns the successor the item names afterwards. `get_by_id` reads the
    item's own catalogue, archived rows included."""
    successor_id = successor_to_check(change)
    facts = None
    if successor_id is not None:
        facts = await load_successor_facts(get_by_id, successor_id)
    return assert_catalogue_status_change(change, facts)
