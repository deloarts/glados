"""The actions a user can take on a lifecycle aggregate: an order, an order
item, a production lot, a lot position, a production order, a demand, a
quote request or a project.

The intent tables in src/modules/fulfillment/domain/services/lifecycle/intents.py decide which of
these actions a given user may take on a given aggregate. One evaluation of
those tables serves both a use case's guard and the list of actions a client
is offered, so the two cannot disagree. One value can apply to several
aggregates, for example CANCEL on an order, a lot or a demand.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class LifecycleAction(StrValueEnum):
    """One user intent on a lifecycle aggregate."""

    DELIVER = "deliver"
    CORRECT_DELIVERY = "correct_delivery"
    CLOSE_SHORT = "close_short"
    REOPEN = "reopen"
    CANCEL = "cancel"
    HOLD = "hold"
    RESUME = "resume"
    FORCE_COMPLETE = "force_complete"
    START = "start"
    PAUSE = "pause"
    RECORD_COMPLETION = "record_completion"
    REVERSE_COMPLETION = "reverse_completion"
    MARK_REQUESTED = "mark_requested"
    MARK_ORDERED = "mark_ordered"
    MARK_READY_FOR_PICKUP = "mark_ready_for_pickup"
    FULFIL = "fulfil"
    ALLOCATE = "allocate"
    EDIT_QUANTITY = "edit_quantity"
    EDIT_STRUCTURE = "edit_structure"
    REORDER_POSITIONS = "reorder_positions"
    MOVE = "move"
    REMOVE = "remove"
    SCRAP = "scrap"
    SPLIT = "split"
    MERGE = "merge"
    ASSIGN_EXTERNAL = "assign_external"
    ASSIGN_INTERNAL = "assign_internal"
    UNASSIGN_EXTERNAL = "unassign_external"
    RECORD_PROVISION = "record_provision"
    SEND = "send"
    AWARD = "award"
    CLOSE = "close"
    APPROVE_SOURCE = "approve_source"
    REJECT_SOURCE = "reject_source"
    SWITCH_SOURCE = "switch_source"
    COMPLETE = "complete"
    ARCHIVE = "archive"
    EDIT = "edit"
    ADD_ITEM = "add_item"
