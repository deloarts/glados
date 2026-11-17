"""The order of a hand-ordered list: one place up or down per move, past
entries of the other archived state, or next to a named neighbour as a
drag does, renumbered from 0."""

from dataclasses import dataclass

import pytest

from src.shared_kernel.domain.services.list_order import changed_sort_orders
from src.shared_kernel.domain.services.list_order import move_entry
from src.shared_kernel.domain.services.list_order import place_entry
from src.shared_kernel.domain.value_objects.list_move_direction import ListMoveDirection


@dataclass
class _Entry:
    id: int
    sort_order: int
    archived: bool = False


def test_list_order_move_swaps_and_renumbers() -> None:
    entries = [_Entry(1, 0), _Entry(2, 5), _Entry(3, 5)]

    ordered = move_entry(entries, 3, ListMoveDirection.UP)

    assert [(e.id, e.sort_order) for e in ordered] == [(1, 0), (3, 1), (2, 2)]


def test_list_order_move_passes_entries_of_the_other_archived_state() -> None:
    entries = [_Entry(1, 0), _Entry(2, 1, archived=True), _Entry(3, 2)]

    assert [e.id for e in move_entry(entries, 3, ListMoveDirection.UP)] == [3, 2, 1]


def test_list_order_move_keeps_the_ends_and_refuses_an_unknown_entry() -> None:
    entries = [_Entry(1, 0), _Entry(2, 1)]

    assert [e.id for e in move_entry(entries, 1, ListMoveDirection.UP)] == [1, 2]
    assert [e.id for e in move_entry(entries, 2, ListMoveDirection.DOWN)] == [1, 2]
    with pytest.raises(ValueError):
        move_entry(entries, 99, ListMoveDirection.UP)


def test_list_order_changed_sort_orders_names_only_moved_entries() -> None:
    entries = [_Entry(1, 0), _Entry(2, 1), _Entry(3, 2)]
    before = {e.id: e.sort_order for e in entries}

    ordered = move_entry(entries, 3, ListMoveDirection.UP)

    assert changed_sort_orders(before, ordered) == {3: 1, 2: 2}


def test_list_order_place_after_a_neighbour_moves_several_places() -> None:
    entries = [_Entry(1, 0), _Entry(2, 1), _Entry(3, 2), _Entry(4, 3)]

    ordered = place_entry(entries, 1, after_id=3)

    assert [(e.id, e.sort_order) for e in ordered] == [(2, 0), (3, 1), (1, 2), (4, 3)]


def test_list_order_place_before_a_neighbour_or_first() -> None:
    entries = [_Entry(1, 0), _Entry(2, 1), _Entry(3, 2)]

    assert [e.id for e in place_entry(entries, 3, before_id=2)] == [1, 3, 2]
    assert [e.id for e in place_entry(entries, 2)] == [2, 1, 3]


def test_list_order_place_refuses_an_unknown_entry_or_neighbour() -> None:
    entries = [_Entry(1, 0), _Entry(2, 1)]

    with pytest.raises(ValueError):
        place_entry(entries, 99, after_id=1)
    with pytest.raises(ValueError):
        place_entry(entries, 1, after_id=99)
