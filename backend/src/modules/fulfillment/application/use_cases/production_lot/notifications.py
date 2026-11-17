"""
Who learns about scrapped pieces, the supplier lines an ended lot left to
settle and a lot that ended short. Registered at startup through
src/bootstrap/registrations.py.
"""

from src.modules.fulfillment.domain.events.lot_events import LotEndedShort
from src.modules.fulfillment.domain.events.lot_events import LotSupplierLinesToSettle
from src.modules.fulfillment.domain.events.lot_events import PiecesScrapped
from src.modules.platform.application.services.notification_rules import NotificationRule
from src.modules.platform.application.services.notification_rules import NotificationSender
from src.modules.platform.domain.entities.notification import make_notification
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind
from src.modules.platform.domain.value_objects.notification_type import NotificationType
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.events.base import DomainEvent


async def _on_pieces_scrapped(
    sender: NotificationSender, event: PiecesScrapped, source_event_id: str
) -> None:
    message = f"{event.quantity:.3f} piece(s) scrapped on lot {event.lot_number}: {event.reason}."
    if event.replacement_lot_number:
        message = (
            f"Replacement lot {event.replacement_lot_number} created for "
            f"{event.lot_number}: {event.reason}, {event.quantity:.3f} piece(s)."
        )
    for user in await sender.users_with_permission(Permission.MANAGE_LOTS):
        await sender.notify(
            make_notification(
                user_id=user.id,
                type=NotificationType.PIECES_SCRAPPED,
                title="Pieces scrapped",
                message=message,
                source_event_id=source_event_id,
            )
        )


async def _on_supplier_lines_to_settle(
    sender: NotificationSender, event: LotSupplierLinesToSettle, source_event_id: str
) -> None:
    """Purchasing, everyone who writes orders, learns which supplier
    lines an ended lot left to settle, in the app and by mail."""
    ended = {"canceled": "canceled", "scrapped": "scrapped to nothing"}.get(
        event.ended, "force-completed"
    )
    parts = []
    if event.open_lines:
        parts.append(f"still open: {', '.join(event.open_lines)}")
    if event.canceled_lines:
        parts.append(f"canceled although ordered: {', '.join(event.canceled_lines)}")
    message = (
        f"Lot {event.lot_number} was {ended}; settle its supplier lines with the "
        f"supplier ({'; '.join(parts)})."
    )
    recipients = await sender.users_with_permission(Permission.WRITE_ORDERS)
    for user in recipients:
        await sender.notify(
            make_notification(
                user_id=user.id,
                type=NotificationType.SUPPLIER_LINES_TO_SETTLE,
                title="Supplier lines to settle",
                message=message,
                order_id=event.order_id,
                source_event_id=source_event_id,
            )
        )
    await sender.commit()
    if not await sender.mail_enabled():
        return
    for user in recipients:
        await sender.send_mail(
            MailTemplateKind.SUPPLIER_LINES_TO_SETTLE,
            user,
            lot_number=event.lot_number,
            ended=event.ended,
            open_lines=list(event.open_lines),
            canceled_lines=list(event.canceled_lines),
        )


async def _on_lot_ended_short(
    sender: NotificationSender, event: LotEndedShort, source_event_id: str
) -> None:
    """Planners, everyone who manages lots, learn which made demands a
    force-complete left short, which the planning exceptions list too."""
    demands = ", ".join(f"#{i}" for i in event.demand_ids)
    message = (
        f"Lot {event.lot_number} was force-completed at {event.quantity:g} of "
        f"{event.original_quantity:g} piece(s); made demand(s) {demands} are short."
    )
    for user in await sender.users_with_permission(Permission.MANAGE_LOTS):
        await sender.notify(
            make_notification(
                user_id=user.id,
                type=NotificationType.LOT_ENDED_SHORT,
                title="Lot ended short",
                message=message,
                source_event_id=source_event_id,
            )
        )


LOT_NOTIFICATION_RULES: dict[type[DomainEvent], NotificationRule] = {
    PiecesScrapped: _on_pieces_scrapped,
    LotSupplierLinesToSettle: _on_supplier_lines_to_settle,
    LotEndedShort: _on_lot_ended_short,
}
