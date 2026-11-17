"""
Unit tests for material_source_rules.resolve_made_item_source_assignment,
the pure decision function behind ApproveLotSource's optional write-back
of an approved lot's source item onto its made item's MadeItem.
source_item_id (see approve_lot_source.py). No I/O, no fakes: every case
here calls the function directly with plain values.
"""

from src.modules.catalogue.domain.policies.material_source_rules import (
    resolve_made_item_source_assignment,
)
from src.modules.catalogue.domain.value_objects.made_item_source_assignment import (
    MadeItemSourceAssignment,
)


def _resolve(
    *,
    assign_enabled: bool = True,
    overwrite_enabled: bool = False,
    lot_source_item_id: int | None = 5,
    made_item_bought_item_id: int | None = None,
    made_item_source_item_id: int | None = None,
    source_item_is_active: bool = True,
    made_item_found: bool = True,
) -> MadeItemSourceAssignment:
    return resolve_made_item_source_assignment(
        assign_enabled=assign_enabled,
        overwrite_enabled=overwrite_enabled,
        lot_source_item_id=lot_source_item_id,
        made_item_bought_item_id=made_item_bought_item_id,
        made_item_source_item_id=made_item_source_item_id,
        source_item_is_active=source_item_is_active,
        made_item_found=made_item_found,
    )


def test_disabled_setting_skips_regardless_of_everything_else():
    assert _resolve(assign_enabled=False) == MadeItemSourceAssignment.SKIPPED_DISABLED
    # Even with an otherwise-clean empty slot and an active source item.
    assert (
        _resolve(assign_enabled=False, made_item_source_item_id=None, source_item_is_active=True)
        == MadeItemSourceAssignment.SKIPPED_DISABLED
    )


def test_lot_with_no_source_item_skips_disabled():
    assert (
        _resolve(assign_enabled=True, lot_source_item_id=None)
        == MadeItemSourceAssignment.SKIPPED_DISABLED
    )


def test_made_item_missing_skips_no_made_item():
    assert _resolve(made_item_found=False) == MadeItemSourceAssignment.SKIPPED_NO_MADE_ITEM


def test_bought_item_present_skips_bought_item_with_overwrite_off():
    assert (
        _resolve(made_item_bought_item_id=7, overwrite_enabled=False)
        == MadeItemSourceAssignment.SKIPPED_BOUGHT_ITEM
    )


def test_bought_item_present_skips_bought_item_with_overwrite_on_too():
    """Rule 2 (pinned): a made item whose bought_item_id is set is NEVER
    touched, in either overwrite mode."""
    assert (
        _resolve(made_item_bought_item_id=7, overwrite_enabled=True)
        == MadeItemSourceAssignment.SKIPPED_BOUGHT_ITEM
    )


def test_empty_slot_assigns():
    assert (
        _resolve(made_item_source_item_id=None, source_item_is_active=True)
        == MadeItemSourceAssignment.ASSIGNED
    )


def test_same_source_item_is_unchanged():
    assert (
        _resolve(lot_source_item_id=5, made_item_source_item_id=5)
        == MadeItemSourceAssignment.UNCHANGED
    )


def test_different_source_item_overwrite_off_skips_existing_source():
    assert (
        _resolve(lot_source_item_id=5, made_item_source_item_id=9, overwrite_enabled=False)
        == MadeItemSourceAssignment.SKIPPED_EXISTING_SOURCE
    )


def test_different_source_item_overwrite_on_assigns():
    assert (
        _resolve(
            lot_source_item_id=5,
            made_item_source_item_id=9,
            overwrite_enabled=True,
            source_item_is_active=True,
        )
        == MadeItemSourceAssignment.ASSIGNED
    )


def test_inactive_source_item_skips_source_inactive():
    assert (
        _resolve(made_item_source_item_id=None, source_item_is_active=False)
        == MadeItemSourceAssignment.SKIPPED_SOURCE_INACTIVE
    )


def test_inactive_source_item_but_already_equal_is_unchanged():
    """Precedence: the UNCHANGED check (made_item already points at this
    exact source item) runs before the active-status check, so an already-
    correct slot is never reported as skipped just because the (already
    assigned) source item has since gone inactive."""
    assert (
        _resolve(lot_source_item_id=5, made_item_source_item_id=5, source_item_is_active=False)
        == MadeItemSourceAssignment.UNCHANGED
    )
