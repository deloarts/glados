"""
HandleEventNotifications for LotEndedShort: every active user who manages
lots, the planners, gets an in-app notification naming the lot and the made
demands its force-complete left short.
"""

from src.modules.fulfillment.domain.events.lot_events import LotEndedShort
from src.modules.platform.application.use_cases.notification.handle_event_notifications import (
    HandleEventNotifications,
)
from src.modules.platform.domain.value_objects.notification_type import NotificationType
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.test_delivery_pieces_rejected_notification import FakeNotificationRepository
from tests.unit.test_delivery_pieces_rejected_notification import FakeUserRepositoryWithPermissions
from tests.unit.test_event_notification_handler import FakeEmailNotificationRepository


async def test_planners_learn_which_made_demands_a_force_complete_left_short() -> None:
    planner = make_user(id=1, permissions=[Permission.MANAGE_LOTS])
    buyer = make_user(id=2, permissions=[Permission.WRITE_ORDERS])
    inapp = FakeNotificationRepository()
    handler = HandleEventNotifications(
        inapp,
        FakeEmailNotificationRepository(),
        user_repo=FakeUserRepositoryWithPermissions([planner, buyer]),
        uow=FakeUnitOfWork(),
    )

    await handler.execute(
        LotEndedShort(
            lot_id=1,
            lot_number="LOT-2026-0001",
            quantity=6.0,
            original_quantity=10.0,
            demand_ids=[3, 4],
            actor_id=99,
        ),
        source_event_id="1-0",
    )

    (notification,) = inapp.saved
    assert notification.user_id == planner.id
    assert notification.type == NotificationType.LOT_ENDED_SHORT
    assert "LOT-2026-0001 was force-completed at 6 of 10" in notification.message
    assert "#3, #4" in notification.message
