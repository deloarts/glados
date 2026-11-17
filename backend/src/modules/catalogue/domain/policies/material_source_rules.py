"""
Shared "at most one material source" invariant, used by both MadeItem
(bought_item_id / source_item_id) and ProductionLot (source_bought_item_id /
source_item_id / source_made_item_id), a catalogue item or a lot may
point at a bought item, a source item, or (for a lot) a made item being
reworked, but never more than one at a time.
"""

from src.modules.catalogue.domain.errors import MaterialSourceConflictError
from src.modules.catalogue.domain.value_objects.made_item_source_assignment import (
    MadeItemSourceAssignment,
)


def assert_at_most_one_material_source(*ids: int | None) -> None:
    if sum(i is not None for i in ids) > 1:
        raise MaterialSourceConflictError("At most one material source may be set at a time.")


def resolve_made_item_source_assignment(
    *,
    assign_enabled: bool,
    overwrite_enabled: bool,
    lot_source_item_id: int | None,
    made_item_bought_item_id: int | None,
    made_item_source_item_id: int | None,
    source_item_is_active: bool,
    made_item_found: bool = True,
) -> MadeItemSourceAssignment:
    """Whether ApproveLotSource's optional write-back may set the approved
    lot's source item onto its made item's MadeItem.source_item_id, and
    what happened if not. Never raises; a skipped write-back is a normal,
    recorded outcome, not an error (see approve_lot_source.py's module
    docstring), because the approval itself, the demand, and
    input_demand_id must always go through regardless of what this
    function decides.

    SKIPPED_SOURCE_INACTIVE mirrors SourceItemCatalogueRules.
    assert_item_active (source_item_rules.py), so the write-back never
    creates catalogue state that UpdateMadeItem would itself reject on a
    later edit (setting an inactive source item is a create/update-time
    validation error there). There is no DB check constraint backing the
    bought/source XOR invariant this module also owns (assert_at_most_one_
    material_source); it lives purely in application code, so this
    function must remain the single place that decides whether the
    write-back is safe, precedence and all; duplicating any part of this
    logic elsewhere risks writing a source item onto a made item the XOR
    invariant, or the active-status rule, would otherwise have refused.

    Precedence, first match wins: when assign_enabled is off, or the lot
    has no source item at all, the result is SKIPPED_DISABLED. When the
    made item could not be loaded, the result is SKIPPED_NO_MADE_ITEM.
    When the made item's material source is a bought item, it is never
    touched, in either overwrite mode, and the result is
    SKIPPED_BOUGHT_ITEM. When the made item already points at this exact
    source item, the result is UNCHANGED (checked before the overwrite-off
    skip below, so an already-correct slot is never reported as
    "skipped"). When the made item points at a *different* source item and
    overwrite is off, the result is SKIPPED_EXISTING_SOURCE. When the
    (approved) source item is not active, the result is
    SKIPPED_SOURCE_INACTIVE. Otherwise, the result is ASSIGNED.
    """
    if not assign_enabled or lot_source_item_id is None:
        return MadeItemSourceAssignment.SKIPPED_DISABLED
    if not made_item_found:
        return MadeItemSourceAssignment.SKIPPED_NO_MADE_ITEM
    if made_item_bought_item_id is not None:
        return MadeItemSourceAssignment.SKIPPED_BOUGHT_ITEM
    if made_item_source_item_id == lot_source_item_id:
        return MadeItemSourceAssignment.UNCHANGED
    if made_item_source_item_id is not None and not overwrite_enabled:
        return MadeItemSourceAssignment.SKIPPED_EXISTING_SOURCE
    if not source_item_is_active:
        return MadeItemSourceAssignment.SKIPPED_SOURCE_INACTIVE
    return MadeItemSourceAssignment.ASSIGNED
