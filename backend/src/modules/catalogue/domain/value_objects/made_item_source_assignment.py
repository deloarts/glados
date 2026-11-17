"""
Outcome enum for the material_source_rules.resolve_made_item_source_
assignment decision (ApproveLotSource's optional write-back of an
approved lot's source item onto its made item's MadeItem.source_item_id).
Recorded, never raised: a skipped write-back is a normal outcome, not an
error, see approve_lot_source.py's module docstring.
"""

from enum import Enum
from enum import unique


@unique
class MadeItemSourceAssignment(str, Enum):
    ASSIGNED = "assigned"
    UNCHANGED = "unchanged"  # already that source item
    SKIPPED_DISABLED = "skipped_disabled"
    # different source item, overwrite off
    SKIPPED_EXISTING_SOURCE = "skipped_existing_source"
    SKIPPED_BOUGHT_ITEM = "skipped_bought_item"
    SKIPPED_SOURCE_INACTIVE = "skipped_source_inactive"
    SKIPPED_NO_MADE_ITEM = "skipped_no_made_item"
