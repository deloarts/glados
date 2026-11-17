"""
HandleEventNotifications for LotSupplierLinesToSettle: every active user who
writes orders, purchasing, gets an in-app notification naming the lot and
the supplier lines left to settle, and a mail of the supplier_lines_to_settle
kind when mail is on.
"""

from src.modules.fulfillment.domain.events.lot_events import LotSupplierLinesToSettle
from src.modules.platform.application.use_cases.notification.handle_event_notifications import (
    HandleEventNotifications,
)
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind
from src.modules.platform.domain.value_objects.notification_type import NotificationType
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.test_delivery_pieces_rejected_notification import FakeNotificationRepository
from tests.unit.test_delivery_pieces_rejected_notification import FakeUserRepositoryWithPermissions
from tests.unit.test_event_notification_handler import FakeAdminSettingsRepoForEvents
from tests.unit.test_event_notification_handler import FakeEmailNotificationRepository
from tests.unit.test_event_notification_handler import FakeMailServiceForEvents

EVENT = LotSupplierLinesToSettle(
    lot_id=1,
    lot_number="LOT-2026-0001",
    ended="canceled",
    open_lines=["B-2026-0003 pos. 2"],
    canceled_lines=["B-2026-0004 pos. 1"],
    order_id=3,
    actor_id=99,
)


def _handler(*, mail_enabled: bool = True):
    buyer = make_user(id=1, permissions=[Permission.WRITE_ORDERS])
    planner = make_user(id=2, permissions=[Permission.MANAGE_LOTS])
    inapp = FakeNotificationRepository()
    mail = FakeMailServiceForEvents()
    handler = HandleEventNotifications(
        inapp,
        FakeEmailNotificationRepository(),
        user_repo=FakeUserRepositoryWithPermissions([buyer, planner]),
        mail_service=mail,
        admin_settings_repo=FakeAdminSettingsRepoForEvents(mail_enabled=mail_enabled),
        uow=FakeUnitOfWork(),
    )
    return handler, inapp, mail, buyer


async def test_purchasing_is_told_in_the_app_which_lines_to_settle() -> None:
    handler, inapp, _, buyer = _handler()

    await handler.execute(EVENT, source_event_id="1-0")

    (notification,) = inapp.saved
    assert notification.user_id == buyer.id
    assert notification.type == NotificationType.SUPPLIER_LINES_TO_SETTLE
    assert notification.order_id == 3
    assert "LOT-2026-0001 was canceled" in notification.message
    assert "still open: B-2026-0003 pos. 2" in notification.message
    assert "canceled although ordered: B-2026-0004 pos. 1" in notification.message


async def test_purchasing_gets_a_mail_naming_the_lines() -> None:
    handler, _, mail, buyer = _handler()

    await handler.execute(EVENT, source_event_id="1-0")

    (sent,) = mail.sent
    assert sent["kind"] == MailTemplateKind.SUPPLIER_LINES_TO_SETTLE
    assert sent["to"] == buyer.email
    assert (sent["lot_number"], sent["ended"]) == ("LOT-2026-0001", "canceled")
    assert sent["open_lines"] == ["B-2026-0003 pos. 2"]
    assert sent["canceled_lines"] == ["B-2026-0004 pos. 1"]


async def test_no_mail_while_mail_is_off() -> None:
    handler, inapp, mail, _ = _handler(mail_enabled=False)

    await handler.execute(EVENT, source_event_id="1-0")

    assert len(inapp.saved) == 1
    assert mail.sent == []
