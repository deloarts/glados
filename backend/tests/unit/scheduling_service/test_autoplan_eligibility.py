"""
Covers which machines and pools Auto-Plan considers eligible for an order, including the
QA-machine gate, fabrication-method capability matching, and pool-level coverage rules.
Unit tests for AutoPlan machine/pool eligibility resolution. No database, no HTTP, pure
functions only.
"""

from src.modules.fulfillment.domain.services.scheduling import machine_covers_fabrication_methods
from src.modules.fulfillment.domain.services.scheduling import resolve_eligible_machine_ids
from src.modules.fulfillment.domain.services.scheduling import resolve_eligible_pool_ids


def test_machine_covers_when_it_has_all_required_methods():
    assert machine_covers_fabrication_methods([1, 2, 3], {1, 2}) is True


def test_machine_does_not_cover_when_missing_a_required_method():
    assert machine_covers_fabrication_methods([1, 2], {1, 2, 3}) is False


def test_machine_covers_empty_requirement_trivially():
    assert machine_covers_fabrication_methods([], set()) is True


def test_resolve_eligible_machine_ids_pool_branch_keeps_only_capable_pool_members():
    result = resolve_eligible_machine_ids(
        order_machine_pool_id=100,
        order_machine_id=None,
        candidate_machine_ids={1, 2, 3},
        pool_machine_ids={1, 2},
        machine_fabrication_method_ids={1: [5], 2: [6], 3: [5]},
        required_fabrication_method_ids={5},
        assign_pool_machines=True,
        assign_machines=False,
    )
    # Machine 3 is capable but not a pool member; machine 2 is a pool
    # member but not capable, only machine 1 qualifies on both counts.
    assert result == [1]


def test_resolve_eligible_machine_ids_pool_branch_never_falls_through_to_any_capable_machine():
    result = resolve_eligible_machine_ids(
        order_machine_pool_id=100,
        order_machine_id=None,
        candidate_machine_ids={1, 2},
        pool_machine_ids={1},
        machine_fabrication_method_ids={1: [], 2: [5]},
        required_fabrication_method_ids={5},
        assign_pool_machines=True,
        assign_machines=True,  # even with assign_machines on, pool orders never fall through
    )
    # Machine 2 is capable and assign_machines=True, but it's not in the
    # pool, the pool branch must win outright, never fall back to "any
    # capable machine".
    assert result == []


def test_resolve_eligible_machine_ids_assign_pool_machines_false_leaves_pool_order_unresolved():
    result = resolve_eligible_machine_ids(
        order_machine_pool_id=100,
        order_machine_id=None,
        candidate_machine_ids={1, 2},
        pool_machine_ids={1, 2},
        machine_fabrication_method_ids={1: [5], 2: [5]},
        required_fabrication_method_ids={5},
        assign_pool_machines=False,
        assign_machines=False,
    )
    assert result == []


def test_resolve_eligible_machine_ids_assign_machines_true_returns_all_capable_candidates():
    result = resolve_eligible_machine_ids(
        order_machine_pool_id=None,
        order_machine_id=None,
        candidate_machine_ids={1, 2, 3},
        pool_machine_ids=set(),
        machine_fabrication_method_ids={1: [5], 2: [6], 3: [5]},
        required_fabrication_method_ids={5},
        assign_pool_machines=True,
        assign_machines=True,
    )
    assert set(result) == {1, 3}


def test_resolve_eligible_machine_ids_default_keeps_only_the_orders_current_machine():
    result = resolve_eligible_machine_ids(
        order_machine_pool_id=None,
        order_machine_id=2,
        candidate_machine_ids={1, 2, 3},
        pool_machine_ids=set(),
        machine_fabrication_method_ids={1: [5], 2: [5], 3: [5]},
        required_fabrication_method_ids={5},
        assign_pool_machines=True,
        assign_machines=False,
    )
    assert result == [2]


def test_resolve_eligible_machine_ids_default_returns_empty_when_no_current_machine():
    result = resolve_eligible_machine_ids(
        order_machine_pool_id=None,
        order_machine_id=None,
        candidate_machine_ids={1, 2, 3},
        pool_machine_ids=set(),
        machine_fabrication_method_ids={1: [5], 2: [5], 3: [5]},
        required_fabrication_method_ids={5},
        assign_pool_machines=True,
        assign_machines=False,
    )
    assert result == []


def test_resolve_eligible_machine_ids_default_returns_empty_when_current_machine_not_capable():
    result = resolve_eligible_machine_ids(
        order_machine_pool_id=None,
        order_machine_id=2,
        candidate_machine_ids={1, 2, 3},
        pool_machine_ids=set(),
        machine_fabrication_method_ids={1: [5], 2: [6], 3: [5]},
        required_fabrication_method_ids={5},
        assign_pool_machines=True,
        assign_machines=False,
    )
    assert result == []


def test_resolve_eligible_machine_ids_default_returns_empty_when_current_machine_not_a_candidate():
    result = resolve_eligible_machine_ids(
        order_machine_pool_id=None,
        order_machine_id=99,
        candidate_machine_ids={1, 2, 3},
        pool_machine_ids=set(),
        machine_fabrication_method_ids={1: [5], 2: [5], 3: [5]},
        required_fabrication_method_ids={5},
        assign_pool_machines=True,
        assign_machines=False,
    )
    assert result == []


def test_resolve_eligible_machine_ids_unassigned_qa_never_eligible_assign_machines_false():
    """A born-internal QA order is machine-less by design and can never
    take the pool path, but that does not make it eligible for the
    capable QA machines here; rule 1b returns `[]` unconditionally. A
    machine reaches it only via the method's default (at creation) or a
    person assigning it by hand, never Auto-Plan."""
    result = resolve_eligible_machine_ids(
        order_machine_pool_id=None,
        order_machine_id=None,
        candidate_machine_ids={1, 2, 3},
        pool_machine_ids=set(),
        machine_fabrication_method_ids={1: [5], 2: [], 3: [5]},
        required_fabrication_method_ids=set(),
        assign_pool_machines=True,
        assign_machines=False,
        qa_machine_ids={2, 3},
        requires_qa_machine=True,
    )
    assert result == []


def test_resolve_eligible_machine_ids_unassigned_qa_never_eligible_assign_machines_true():
    """Sibling to the assign_machines=False case above: rule 1b's early
    `return []` is what makes the rule hold even when assign_machines is
    on, unlike every other kind of unassigned work (which rule 2 would
    otherwise resolve to every capable candidate)."""
    result = resolve_eligible_machine_ids(
        order_machine_pool_id=None,
        order_machine_id=None,
        candidate_machine_ids={1, 2, 3},
        pool_machine_ids=set(),
        machine_fabrication_method_ids={1: [5], 2: [], 3: [5]},
        required_fabrication_method_ids=set(),
        assign_pool_machines=True,
        assign_machines=True,
        qa_machine_ids={2, 3},
        requires_qa_machine=True,
    )
    assert result == []


def test_resolve_eligible_machine_ids_unassigned_fabrication_order_still_skipped():
    """The sibling case to the QA fix above: a non-QA (fabrication) order
    with no current machine keeps today's behavior exactly: it has
    nothing to re-sequence within, so it stays unresolved unless
    assign_machines is explicitly on."""
    result = resolve_eligible_machine_ids(
        order_machine_pool_id=None,
        order_machine_id=None,
        candidate_machine_ids={1, 2, 3},
        pool_machine_ids=set(),
        machine_fabrication_method_ids={1: [5], 2: [], 3: [5]},
        required_fabrication_method_ids={5},
        assign_pool_machines=True,
        assign_machines=False,
        qa_machine_ids={2, 3},
        requires_qa_machine=False,
    )
    assert result == []


def test_resolve_eligible_machine_ids_qa_order_never_resolves_to_a_non_qa_machine():
    """The QA gate still applies to a QA order that already has a machine
    (rule 1b's `[]` only fires for the unassigned case; see the sibling
    tests above): candidates include both QA and plain fabrication
    machines, only the QA one ever comes back for an inspection order,
    even with assign_machines=True considering every candidate."""
    result = resolve_eligible_machine_ids(
        order_machine_pool_id=None,
        order_machine_id=3,
        candidate_machine_ids={1, 2, 3},
        pool_machine_ids=set(),
        machine_fabrication_method_ids={1: [5], 2: [6], 3: []},
        required_fabrication_method_ids=set(),
        assign_pool_machines=True,
        assign_machines=True,
        qa_machine_ids={3},
        requires_qa_machine=True,
    )
    assert result == [3]


def test_resolve_eligible_machine_ids_resolved_qa_order_falls_through_to_rule_3():
    """A QA order that already has a machine (via the method's pre-filled
    default at creation, or a person assigning it by hand, not the
    unassigned case rule 1b targets) falls through to the ordinary rule 3
    unchanged: only re-eligible for the machine it's already on."""
    result = resolve_eligible_machine_ids(
        order_machine_pool_id=None,
        order_machine_id=2,
        candidate_machine_ids={1, 2, 3},
        pool_machine_ids=set(),
        machine_fabrication_method_ids={},
        required_fabrication_method_ids=set(),
        assign_pool_machines=True,
        assign_machines=False,
        qa_machine_ids={2, 3},
        requires_qa_machine=True,
    )
    assert result == [2]


def test_resolve_eligible_pool_ids_covering_pool_is_eligible():
    result = resolve_eligible_pool_ids(
        candidate_pool_ids={1, 2},
        pool_machine_ids={1: [10, 11], 2: [12]},
        machine_fabrication_method_ids={10: [5, 6], 11: [5, 7], 12: [5]},
        required_fabrication_method_ids={5},
    )
    # Pool 1's derived capability = {5,6} ∩ {5,7} = {5}, covers {5}; pool
    # 2's is just {5} (its only member's own methods), covers it too.
    assert set(result) == {1, 2}


def test_resolve_eligible_pool_ids_partial_member_coverage_is_not_eligible():
    """Every member must provide every required method: one member
    lacking method 5 sinks the whole pool's derived capability, even
    though its sibling member does cover it."""
    result = resolve_eligible_pool_ids(
        candidate_pool_ids={1},
        pool_machine_ids={1: [10, 11]},
        machine_fabrication_method_ids={10: [5, 6], 11: [6]},
        required_fabrication_method_ids={5},
    )
    assert result == []


def test_resolve_eligible_pool_ids_empty_pool_is_never_eligible():
    """A pool with no members is never eligible, even against a trivially
    empty requirement that an empty derived capability would otherwise
    vacuously satisfy."""
    result = resolve_eligible_pool_ids(
        candidate_pool_ids={1},
        pool_machine_ids={1: []},
        machine_fabrication_method_ids={},
        required_fabrication_method_ids=set(),
    )
    assert result == []


def test_resolve_eligible_pool_ids_manual_and_inspection_positions_never_pool_eligible():
    """Both guards close the same trap the empty-pool case above closes:
    neither a manual-step nor an inspection position has any real
    fabrication method to check, so an empty required set would otherwise
    make every pool look eligible by vacuous inclusion; QA work and
    manual steps are never pool-eligible outright instead."""
    common = dict(
        candidate_pool_ids={1},
        pool_machine_ids={1: [10]},
        machine_fabrication_method_ids={10: [5]},
        required_fabrication_method_ids=set(),
    )
    assert resolve_eligible_pool_ids(**common, requires_qa_machine=True) == []
    assert resolve_eligible_pool_ids(**common, is_manual_step=True) == []
