"""Notification type taxonomy: demand fulfillment and cancellation, order
cancellation, permission and account changes, project/product assignment,
scrap/goods-receipt-rejection dispositions, document control (editing
taken over or ended by a manager, a revision marked invalid, a new
revision started), mentions and todo assignments in meetings, and agent
tokens that expire soon or were revoked as idle."""

from enum import Enum


class NotificationType(str, Enum):
    DEMAND_ITEM_FULFILLED = "demand_item_fulfilled"
    DEMAND_ITEM_CANCELED = "demand_item_canceled"
    ORDER_CANCELED = "order_canceled"
    PERMISSIONS_CHANGED = "permissions_changed"
    ACCOUNT_DEACTIVATED = "account_deactivated"
    FORCED_LOGOUT = "forced_logout"
    PROJECT_ASSIGNED = "project_assigned"
    PRODUCT_ASSIGNED = "product_assigned"
    PIECES_SCRAPPED = "pieces_scrapped"
    DELIVERY_PIECES_REJECTED = "delivery_pieces_rejected"
    SUPPLIER_LINES_TO_SETTLE = "supplier_lines_to_settle"
    LOT_ENDED_SHORT = "lot_ended_short"
    EDITING_TAKEN_OVER = "editing_taken_over"
    EDITING_ENDED = "editing_ended"
    DOCUMENT_MARKED_INVALID = "document_marked_invalid"
    DOCUMENT_REVISED = "document_revised"
    # An agent token (one carrying use:mcp) that expires within days, and one
    # Glados revoked because it went unused for the agent settings' idle days.
    AGENT_TOKEN_EXPIRING = "agent_token_expiring"
    AGENT_TOKEN_REVOKED = "agent_token_revoked"
    # The mentions and todo assignments of one meeting, bundled per
    # recipient: assigned once any todo was assigned, mentioned otherwise.
    MEETING_MENTIONED = "meeting_mentioned"
    MEETING_TODO_ASSIGNED = "meeting_todo_assigned"
