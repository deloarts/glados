"""
The catalogue status rule: how a write of a catalogue item's status and
successor is accepted, refused or completed, and which items new work may
name. Pure functions, no fakes.
"""

import itertools

import pytest

from src.modules.catalogue.domain.errors import CatalogueStatusChangeError
from src.modules.catalogue.domain.errors import CatalogueSuccessorNotFoundError
from src.modules.catalogue.domain.policies.catalogue_item_status import ACTIVE
from src.modules.catalogue.domain.policies.catalogue_item_status import INACTIVE
from src.modules.catalogue.domain.policies.catalogue_item_status import REPLACED
from src.modules.catalogue.domain.policies.catalogue_item_status import STATUS_MOVES
from src.modules.catalogue.domain.policies.catalogue_item_status import CatalogueStatusChange
from src.modules.catalogue.domain.policies.catalogue_item_status import SuccessorEffect
from src.modules.catalogue.domain.policies.catalogue_item_status import SuccessorFacts
from src.modules.catalogue.domain.policies.catalogue_item_status import (
    assert_catalogue_status_change,
)
from src.modules.catalogue.domain.policies.catalogue_item_status import assert_new_item_status
from src.modules.catalogue.domain.policies.catalogue_item_status import demandable_refusal
from src.modules.catalogue.domain.policies.catalogue_item_status import successor_to_check
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus

ITEM = 1
_ACTIVE = BoughtItemCatalogueStatus.ACTIVE
_INACTIVE = BoughtItemCatalogueStatus.INACTIVE
_REPLACED = BoughtItemCatalogueStatus.REPLACED


def _change(
    old: str | None,
    new: str,
    old_successor: int | None = None,
    requested: int | None = None,
    *,
    pdm_owned: bool = False,
) -> CatalogueStatusChange:
    return CatalogueStatusChange(
        family="bought item",
        item_id=ITEM if old is not None else None,
        old_status=BoughtItemCatalogueStatus(old) if old is not None else None,
        old_successor_id=old_successor,
        new_status=BoughtItemCatalogueStatus(new),
        requested_successor_id=requested,
        status_owned_by_pdm=pdm_owned,
    )


def _live(successor_id: int, *chain: int) -> SuccessorFacts:
    return SuccessorFacts(id=successor_id, archived=False, chain=chain)


# ── The move table ───────────────────────────────────────────────────────


def test_the_three_catalogues_share_the_statuses_the_rule_knows():
    for enum in (MadeItemCatalogueStatus, BoughtItemCatalogueStatus, SourceItemCatalogueStatus):
        assert {member.value for member in enum} == {ACTIVE, INACTIVE, REPLACED}


def test_every_move_between_two_statuses_and_every_creation_is_listed_once():
    statuses = (ACTIVE, INACTIVE, REPLACED)
    expected = {(a, b) for a, b in itertools.permutations(statuses, 2)} | {
        (None, status) for status in statuses
    }
    listed = [(move.from_status, move.to_status) for move in STATUS_MOVES]
    assert sorted(listed, key=str) == sorted(expected, key=str)


def test_only_a_move_to_replaced_requires_a_successor():
    for move in STATUS_MOVES:
        required = move.successor is SuccessorEffect.REQUIRED
        assert required == (move.to_status == REPLACED)
        assert move.effect


def test_replaced_may_move_to_inactive_and_drops_its_successor():
    assert assert_catalogue_status_change(_change(REPLACED, INACTIVE, 7, 7), None) is None


# ── The rule over every combination ─────────────────────────────────────


def _expected(
    old: str | None, new: str, old_successor: int | None, requested: int | None, pdm_owned: bool
) -> int | type[Exception] | None:
    """The rule written out independently: what the item names afterwards,
    or the error class, when every named successor is valid."""
    if new == old and requested == old_successor:
        return old_successor
    if new != REPLACED:
        if requested is not None and requested != old_successor:
            return CatalogueStatusChangeError
        return None
    if requested is None:
        if old == REPLACED and pdm_owned:
            return None
        return CatalogueStatusChangeError
    return requested


_COMBINATIONS = [
    (old, new, old_successor, requested, pdm_owned)
    for old in (None, ACTIVE, INACTIVE, REPLACED)
    for new in (ACTIVE, INACTIVE, REPLACED)
    for old_successor in ((None,) if old is None else (None, 5))
    for requested in (None, 5, 6)
    for pdm_owned in (False, True)
]


@pytest.mark.parametrize(("old", "new", "old_successor", "requested", "pdm_owned"), _COMBINATIONS)
def test_every_combination_follows_the_rule(old, new, old_successor, requested, pdm_owned):
    change = _change(old, new, old_successor, requested, pdm_owned=pdm_owned)
    to_check = successor_to_check(change)
    facts = _live(to_check) if to_check is not None else None
    expected = _expected(old, new, old_successor, requested, pdm_owned)

    if expected is CatalogueStatusChangeError:
        with pytest.raises(CatalogueStatusChangeError):
            assert_catalogue_status_change(change, facts)
    else:
        assert assert_catalogue_status_change(change, facts) == expected


@pytest.mark.parametrize(("old", "new", "old_successor", "requested", "pdm_owned"), _COMBINATIONS)
def test_only_a_successor_the_write_newly_names_for_a_replaced_item_is_checked(
    old, new, old_successor, requested, pdm_owned
):
    change = _change(old, new, old_successor, requested, pdm_owned=pdm_owned)
    unchanged = new == old and requested == old_successor
    expected = requested if new == REPLACED and requested is not None and not unchanged else None
    assert successor_to_check(change) == expected


# ── The successor itself ────────────────────────────────────────────────


def test_a_successor_that_does_not_exist_is_not_found():
    with pytest.raises(CatalogueSuccessorNotFoundError, match="#9"):
        assert_catalogue_status_change(_change(ACTIVE, REPLACED, None, 9), None)


def test_an_item_cannot_be_its_own_successor():
    with pytest.raises(CatalogueStatusChangeError, match="its own successor"):
        assert_catalogue_status_change(_change(ACTIVE, REPLACED, None, ITEM), _live(ITEM))


def test_a_successor_that_leads_back_to_the_item_is_refused():
    # 5 is followed by 6 and then by the item itself.
    with pytest.raises(CatalogueStatusChangeError, match="loop"):
        assert_catalogue_status_change(_change(ACTIVE, REPLACED, None, 5), _live(5, 6, ITEM))


def test_a_chain_that_does_not_reach_the_item_is_fine():
    assert assert_catalogue_status_change(_change(ACTIVE, REPLACED, None, 5), _live(5, 6, 7)) == 5


def test_an_archived_successor_is_refused():
    archived = SuccessorFacts(id=5, archived=True)
    with pytest.raises(CatalogueStatusChangeError, match="archived"):
        assert_catalogue_status_change(_change(INACTIVE, REPLACED, None, 5), archived)


def test_a_replaced_item_may_point_at_another_live_successor():
    assert assert_catalogue_status_change(_change(REPLACED, REPLACED, 5, 6), _live(6)) == 6


def test_a_replaced_item_cannot_point_at_an_archived_successor():
    with pytest.raises(CatalogueStatusChangeError, match="archived"):
        assert_catalogue_status_change(
            _change(REPLACED, REPLACED, 5, 6), SuccessorFacts(id=6, archived=True)
        )


# ── Messages and edge cases ──────────────────────────────────────────────


def test_a_replaced_row_whose_status_the_caller_owns_keeps_its_successor():
    with pytest.raises(CatalogueStatusChangeError, match="keeps a successor"):
        assert_catalogue_status_change(_change(REPLACED, REPLACED, 5, None), None)


def test_a_replaced_row_whose_status_pdm_owns_may_drop_its_successor():
    change = _change(REPLACED, REPLACED, 5, None, pdm_owned=True)
    assert assert_catalogue_status_change(change, None) is None


def test_only_a_replaced_item_names_a_successor():
    with pytest.raises(CatalogueStatusChangeError, match="only a replaced item"):
        assert_catalogue_status_change(_change(ACTIVE, ACTIVE, None, 5), _live(5))


def test_an_unchanged_write_leaves_an_older_inconsistent_row_alone():
    assert assert_catalogue_status_change(_change(REPLACED, REPLACED, None, None), None) is None
    assert assert_catalogue_status_change(_change(ACTIVE, ACTIVE, 5, 5), None) == 5


def test_an_unknown_status_is_refused_before_it_reaches_the_rule():
    with pytest.raises(ValueError, match="retired"):
        _change(ACTIVE, "retired")


@pytest.mark.parametrize("status", [ACTIVE, INACTIVE])
def test_a_new_item_may_start_active_or_inactive(status):
    assert_new_item_status(family="source item", status=SourceItemCatalogueStatus(status))


def test_a_new_item_cannot_start_replaced_since_it_names_no_successor():
    with pytest.raises(CatalogueStatusChangeError, match="A new source item needs a successor"):
        assert_new_item_status(family="source item", status=SourceItemCatalogueStatus.REPLACED)


# ── Which items new work may name ───────────────────────────────────────


@pytest.mark.parametrize(
    ("status", "archived", "sync_state", "reason"),
    [
        (_ACTIVE, False, None, None),
        (_ACTIVE, False, PdmSyncState.SYNCED, None),
        (_ACTIVE, False, PdmSyncState.CONFLICT, None),
        (_INACTIVE, False, None, "is inactive"),
        (_REPLACED, False, None, "is replaced"),
        (_ACTIVE, True, None, "is archived"),
        (_INACTIVE, True, None, "is archived"),
        (_ACTIVE, False, PdmSyncState.MISSING, "is missing in PDM"),
    ],
)
def test_new_work_needs_an_active_live_item_whose_file_is_not_missing(
    status, archived, sync_state, reason
):
    assert demandable_refusal(status=status, archived=archived, pdm_sync_state=sync_state) == reason
