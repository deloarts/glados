"""Event types of the lot audit trail, one per mutation use case. Granular
on purpose, because an ISO 9001 audit must tell an edited step from a
deleted one."""

from enum import Enum
from enum import unique


@unique
class LotEventType(str, Enum):
    """What kind of thing happened to a lot (or one of its owned children)."""

    # ── Lot ──────────────────────────────────────────────────────────
    LOT_CREATED = "lot_created"
    LOT_UPDATED = "lot_updated"
    LOT_MATERIAL_SOURCE_SWITCHED = "lot_material_source_switched"
    LOT_CANCELED = "lot_canceled"
    LOT_COMPLETED = "lot_completed"
    LOT_HELD = "lot_held"
    LOT_RESUMED = "lot_resumed"
    # Written by the lifecycle reconciler: SCRAPPED when nothing is left to
    # produce, STATUS_CHANGED for any other change the facts bring about.
    LOT_SCRAPPED = "lot_scrapped"
    LOT_STATUS_CHANGED = "lot_status_changed"
    # LOT_SOURCE_APPROVED carries the created demand, the made item and
    # whether the source was also written onto it.
    LOT_SOURCE_APPROVED = "lot_source_approved"
    LOT_SOURCE_REJECTED = "lot_source_rejected"
    # Inspection dispositions, recorded on the origin lot.
    LOT_CLOSED_SHORT = "lot_closed_short"
    REWORK_LOT_CREATED = "rework_lot_created"
    REPLACEMENT_LOT_CREATED = "replacement_lot_created"
    # REPLACEMENT_SKIPPED means the operator declined a replacement lot, so
    # demand coverage was reduced instead.
    PIECES_SCRAPPED = "pieces_scrapped"
    REPLACEMENT_SKIPPED = "replacement_skipped"
    # Pieces rejected as lost when receiving a MADE line.
    PIECES_LOST_AT_RECEIPT = "pieces_lost_at_receipt"
    # A force-complete drops the pieces finished at a position that did not
    # reach the next one, and a lot that ends leaves raw material that
    # arrived but was not used; both are recorded so the loss is on file.
    WIP_DROPPED = "wip_dropped"
    RAW_MATERIAL_LEFT_OVER = "raw_material_left_over"

    # ── Positions ────────────────────────────────────────────────────
    POSITIONS_REGROUPED = "positions_regrouped"
    POSITION_APPENDED = "position_appended"
    POSITION_ASSIGNED_EXTERNAL = "position_assigned_external"
    POSITION_UNASSIGNED_EXTERNAL = "position_unassigned_external"
    POSITION_PROVISION_RECORDED = "position_provision_recorded"
    POSITION_ASSIGNED_INTERNAL = "position_assigned_internal"

    # ── Steps ────────────────────────────────────────────────────────
    STEP_ADDED = "step_added"
    STEP_UPDATED = "step_updated"
    STEP_DELETED = "step_deleted"
    STEPS_REORDERED = "steps_reordered"

    # ── Production orders (internal positions) ──────────────────────
    ORDER_STARTED = "order_started"
    ORDER_PAUSED = "order_paused"
    ORDER_CANCELED = "order_canceled"
    ORDER_SPLIT = "order_split"
    ORDER_MERGED = "order_merged"
    ORDER_COMPLETION_RECORDED = "order_completion_recorded"
    ORDER_COMPLETION_REVERSED = "order_completion_reversed"
    # Emitted in addition to ORDER_COMPLETION_RECORDED for an inspection.
    INSPECTION_RECORDED = "inspection_recorded"
