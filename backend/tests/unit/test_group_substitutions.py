"""
Unit tests for group_substitutions
(src/modules/fulfillment/application/services/allocation_lookup.py), which
totals the substituting allocations of a demand per substitute.
"""

from dataclasses import dataclass

from src.modules.fulfillment.application.services.allocation_lookup import group_substitutions


@dataclass
class _Allocation:
    substitute_id: int | None
    quantity: float
    substitute_reason: str | None = None


def test_group_substitutions_sums_per_substitute_in_first_seen_order():
    allocations = [
        _Allocation(substitute_id=7, quantity=2.0),
        _Allocation(substitute_id=None, quantity=9.0, substitute_reason="ignored"),
        _Allocation(substitute_id=3, quantity=1.0, substitute_reason="cheaper"),
        _Allocation(substitute_id=7, quantity=0.5, substitute_reason="out of stock"),
        _Allocation(substitute_id=7, quantity=1.5, substitute_reason="later"),
    ]

    groups = group_substitutions(allocations, lambda a: a.substitute_id)

    assert list(groups) == [7, 3]
    assert groups[7] == ("out of stock", 4.0)
    assert groups[3] == ("cheaper", 1.0)


def test_group_substitutions_is_empty_without_substitutes():
    allocations = [_Allocation(substitute_id=None, quantity=1.0)]

    assert group_substitutions(allocations, lambda a: a.substitute_id) == {}
