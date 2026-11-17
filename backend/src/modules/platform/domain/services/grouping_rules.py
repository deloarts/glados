"""
Shared contiguous-grouping validation for aggregates that partition an
ordered list of child items into ordered groups: LotStep -> LotPosition
(lot_rules.validate_position_grouping) and MadeItemProcess -> routing
group (made_item_rules.validate_process_grouping). Both callers pass
their own entity accessors, exception class and vocabulary so the two
call sites raise their own distinct error messages from this one
implementation. No I/O.
"""

from collections.abc import Callable
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")

ErrorFactory = Callable[[str], Exception]


def validate_contiguous_grouping(
    items: Sequence[T],
    groups: list[list[int]],
    *,
    item_id: Callable[[T], int],
    item_order: Callable[[T], int],
    is_inspection: Callable[[T], bool],
    error_factory: ErrorFactory,
    item_noun: str,
    group_noun: str,
    owner_noun: str,
    order_noun: str,
) -> None:
    """Validates that `groups`, an ordered list of item-id lists, covers
    every item in `items` exactly once and that, sorted by item_order, the
    groups form contiguous, gapless, correctly-ordered slices of the item
    list. An item for which is_inspection is true can never share a group
    with any other item, regardless of that other item's own inspection
    status: a QA checkpoint is always its own group, never folded into
    another one. Raises error_factory(message); item_noun (e.g. "step"),
    group_noun (e.g. "position group"), owner_noun (e.g. "this lot") and
    order_noun (e.g. "sequence") shape the message to match the caller's
    domain vocabulary."""
    if not groups:
        raise error_factory(f"At least one {group_noun} is required.")

    by_id = {item_id(item): item for item in items}
    seen = _assert_membership(groups, by_id, error_factory, item_noun, group_noun, owner_noun)
    _assert_no_inspection_sharing(groups, by_id, is_inspection, error_factory, item_noun)
    _assert_full_coverage(seen, set(by_id), error_factory, item_noun)
    _assert_contiguous_order(
        items, groups, item_id, item_order, error_factory, item_noun, order_noun
    )


def _assert_membership(
    groups: list[list[int]],
    by_id: dict[int, T],
    error_factory: ErrorFactory,
    item_noun: str,
    group_noun: str,
    owner_noun: str,
) -> set[int]:
    """Every group is non-empty, every id in it belongs to the aggregate,
    and no id appears in more than one group. Returns the set of ids seen
    across all groups, for the caller's full-coverage check."""
    seen: set[int] = set()
    for group in groups:
        if not group:
            raise error_factory(f"A {group_noun} must cover at least one {item_noun}.")
        for item_id_value in group:
            if item_id_value not in by_id:
                raise error_factory(
                    f"{item_noun.capitalize()} #{item_id_value} does not belong to {owner_noun}."
                )
            if item_id_value in seen:
                raise error_factory(
                    f"{item_noun.capitalize()} #{item_id_value} appears in more than one group."
                )
            seen.add(item_id_value)
    return seen


def _assert_no_inspection_sharing(
    groups: list[list[int]],
    by_id: dict[int, T],
    is_inspection: Callable[[T], bool],
    error_factory: ErrorFactory,
    item_noun: str,
) -> None:
    """An inspection item can never share a multi-item group with anything
    else, fabrication or inspection alike."""
    for group in groups:
        if len(group) <= 1:
            continue
        for item_id_value in group:
            if is_inspection(by_id[item_id_value]):
                raise error_factory(
                    f"{item_noun.capitalize()} #{item_id_value} is an inspection step and "
                    f"cannot share a group with any other {item_noun}."
                )


def _assert_full_coverage(
    seen: set[int], all_ids: set[int], error_factory: ErrorFactory, item_noun: str
) -> None:
    """Every item in the aggregate must be covered by exactly one group;
    _assert_membership already ruled out double coverage, so this only
    catches items left out entirely."""
    if seen != all_ids:
        missing = sorted(all_ids - seen)
        raise error_factory(
            f"Every {item_noun} must be covered by exactly one group; missing: {missing}."
        )


def _assert_contiguous_order(
    items: Sequence[T],
    groups: list[list[int]],
    item_id: Callable[[T], int],
    item_order: Callable[[T], int],
    error_factory: ErrorFactory,
    item_noun: str,
    order_noun: str,
) -> None:
    """Sorted by item_order, the groups must be gapless, correctly-ordered
    slices of the item list: group N's items must be exactly the next
    len(group) items after group N-1's, in order."""
    ordered = sorted(items, key=item_order)
    cursor = 0
    for group in groups:
        group_size = len(group)
        slice_ids = {item_id(item) for item in ordered[cursor : cursor + group_size]}
        if slice_ids != set(group):
            raise error_factory(
                f"Groups must cover contiguous, {order_noun}-ordered slices of the "
                f"{item_noun} list."
            )
        cursor += group_size
