"""
The order of a hand-ordered list, such as the article groups or the
production machines, whose entries pickers offer in a sequence the users
set by moving an entry up or down. No I/O.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import TypeVar

from src.shared_kernel.domain.value_objects.list_move_direction import ListMoveDirection


class OrderedEntry(Protocol):
    id: int
    archived: bool
    sort_order: int


TEntry = TypeVar("TEntry", bound=OrderedEntry)


@dataclass
class ListEntry:
    """One row's place in a hand-ordered list, all a move needs to know."""

    id: int
    sort_order: int
    archived: bool


def move_entry(entries: list[TEntry], entry_id: int, direction: ListMoveDirection) -> list[TEntry]:
    """Moves one entry of a hand-ordered list one place up or down and
    returns the list in its new order, with every `sort_order` rewritten to
    0, 1, 2 and so on, which also settles any ties.

    The entry trades places with its nearest neighbour of the same archived
    state, so a live entry passes archived ones, which no picker offers, in
    a single step. An entry already first or last stays where it is. The
    caller makes sure the entry is part of the list; a missing one is a
    programming error and raises ValueError."""
    ordered = sorted(entries, key=lambda entry: (entry.sort_order, entry.id))
    index = next((i for i, entry in enumerate(ordered) if entry.id == entry_id), None)
    if index is None:
        raise ValueError(f"Entry #{entry_id} is not part of this list.")
    archived = ordered[index].archived
    peers = [i for i, entry in enumerate(ordered) if entry.archived == archived]
    target = peers.index(index) + (-1 if direction is ListMoveDirection.UP else 1)
    if 0 <= target < len(peers):
        other = peers[target]
        ordered[index], ordered[other] = ordered[other], ordered[index]
    for position, entry in enumerate(ordered):
        entry.sort_order = position
    return ordered


def place_entry(
    entries: list[TEntry],
    entry_id: int,
    *,
    after_id: int | None = None,
    before_id: int | None = None,
) -> list[TEntry]:
    """Puts one entry of a hand-ordered list directly after `after_id`, or
    directly before `before_id` when no `after_id` is given, and returns the
    list in its new order with every `sort_order` rewritten to 0, 1, 2 and
    so on. This is what dragging a row onto a new place does; naming the
    neighbour rather than a position keeps it right however the screen
    filters or pages the list. With neither neighbour the entry goes first.
    The caller makes sure every id is part of the list; a missing one is a
    programming error and raises ValueError."""
    ordered = sorted(entries, key=lambda entry: (entry.sort_order, entry.id))
    moved = next((entry for entry in ordered if entry.id == entry_id), None)
    if moved is None:
        raise ValueError(f"Entry #{entry_id} is not part of this list.")
    rest = [entry for entry in ordered if entry.id != entry_id]
    anchor_id = after_id if after_id is not None else before_id
    if anchor_id is None:
        index = 0
    else:
        anchor = next((i for i, entry in enumerate(rest) if entry.id == anchor_id), None)
        if anchor is None:
            raise ValueError(f"Entry #{anchor_id} is not part of this list.")
        index = anchor + 1 if after_id is not None else anchor
    rest.insert(index, moved)
    for position, entry in enumerate(rest):
        entry.sort_order = position
    return rest


def changed_sort_orders(before: dict[int, int], ordered: list[TEntry]) -> dict[int, int]:
    """The new `sort_order` of every entry whose position changed, by id,
    given each entry's `sort_order` before the move."""
    return {e.id: e.sort_order for e in ordered if e.sort_order != before.get(e.id)}
