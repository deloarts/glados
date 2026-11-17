"""
Unit test for HandleEventNotifications' DeliveryPiecesRejected handling
(goods-receipt rejection): an in-app notification to every active user
holding write:orders, mirroring test_pieces_scrapped_notification.py's
own shape for PiecesScrapped (manage:lots): a broadcast to every
permission holder, not just one already-known user_id.
"""

from src.modules.fulfillment.domain.events.order_events import DeliveryPiecesRejected
from src.modules.platform.application.use_cases.notification.handle_event_notifications import (
    HandleEventNotifications,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.notification_type import NotificationType
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.repositories.user_repository import UserFilterDto
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork


class FakeNotificationRepository:
    def __init__(self) -> None:
        self.saved: list = []

    async def exists_by_source_event_id(self, source_event_id: str) -> bool:
        return False

    async def save(self, notification):
        self.saved.append(notification)
        return notification

    async def add_for_event(self, notification):
        self.saved.append(notification)
        return True


class FakeEmailNotificationRepository:
    async def save(self, notification):
        raise AssertionError("DeliveryPiecesRejected never writes an email digest entry.")


class FakeUserRepositoryWithPermissions:
    def __init__(self, users: list[User]) -> None:
        self._users = users

    async def get_multi(self, filters: UserFilterDto) -> tuple[int, list[User]]:
        active = [u for u in self._users if u.is_active]
        total = len(active)
        skip = filters.skip or 0
        limit = filters.limit or total
        return total, active[skip : skip + limit]


async def test_delivery_pieces_rejected_notifies_every_write_orders_holder_not_others() -> None:
    order_writer_a = make_user(id=1, permissions=[Permission.WRITE_ORDERS])
    order_writer_b = make_user(id=2, permissions=[Permission.WRITE_ORDERS])
    non_writer = make_user(id=3, permissions=[Permission.RECEIVE_DELIVERIES])
    user_repo = FakeUserRepositoryWithPermissions([order_writer_a, order_writer_b, non_writer])

    inapp = FakeNotificationRepository()
    handler = HandleEventNotifications(
        inapp, FakeEmailNotificationRepository(), user_repo=user_repo, uow=FakeUnitOfWork()
    )

    event = DeliveryPiecesRejected(
        order_item_id=1,
        order_id=2,
        supplier_id=3,
        quantity=1.0,
        reason="supplier_damage",
        outcome="lost",
        actor_id=99,
    )

    await handler.execute(event, source_event_id="stream-id-1")

    notified_user_ids = {n.user_id for n in inapp.saved}
    assert notified_user_ids == {order_writer_a.id, order_writer_b.id}
    for notification in inapp.saved:
        assert notification.type == NotificationType.DELIVERY_PIECES_REJECTED
        assert notification.order_id == 2
        assert "supplier_damage" in notification.message
        assert "lost" in notification.message


async def test_delivery_pieces_rejected_message_mentions_order_item_and_quantity() -> None:
    order_writer = make_user(id=1, permissions=[Permission.WRITE_ORDERS])
    user_repo = FakeUserRepositoryWithPermissions([order_writer])
    inapp = FakeNotificationRepository()
    handler = HandleEventNotifications(
        inapp, FakeEmailNotificationRepository(), user_repo=user_repo, uow=FakeUnitOfWork()
    )

    event = DeliveryPiecesRejected(
        order_item_id=42,
        order_id=7,
        supplier_id=3,
        quantity=2.0,
        reason="wrong_spec",
        outcome="redeliver",
        actor_id=99,
    )

    await handler.execute(event, source_event_id="stream-id-2")

    assert len(inapp.saved) == 1
    assert "42" in inapp.saved[0].message
    assert "2.000" in inapp.saved[0].message
