"""
Unit test for HandleEventNotifications' PiecesScrapped handling: an
in-app notification to every active user holding manage:lots, not just
one already-known user_id like every other event this handler processes;
see _users_with_permission's own pagination note. A separate file from
test_event_notification_handler.py
since that file's FakeUserRepositoryForEvents only implements get_by_id,
not the get_multi paging this handler's broadcast needs.
"""

from src.modules.fulfillment.domain.events.lot_events import PiecesScrapped
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
        raise AssertionError("PiecesScrapped never writes an email digest entry.")


class FakeUserRepositoryWithPermissions:
    def __init__(self, users: list[User]) -> None:
        self._users = users

    async def get_multi(self, filters: UserFilterDto) -> tuple[int, list[User]]:
        active = [u for u in self._users if u.is_active]
        total = len(active)
        skip = filters.skip or 0
        limit = filters.limit or total
        return total, active[skip : skip + limit]


async def test_pieces_scrapped_notifies_every_manage_lots_holder_not_others() -> None:
    manager_a = make_user(id=1, permissions=[Permission.MANAGE_LOTS])
    manager_b = make_user(id=2, permissions=[Permission.MANAGE_LOTS])
    non_manager = make_user(id=3, permissions=[Permission.WRITE_PRODUCTION_ORDERS])
    user_repo = FakeUserRepositoryWithPermissions([manager_a, manager_b, non_manager])

    inapp = FakeNotificationRepository()
    handler = HandleEventNotifications(
        inapp, FakeEmailNotificationRepository(), user_repo=user_repo, uow=FakeUnitOfWork()
    )

    event = PiecesScrapped(
        lot_id=1,
        lot_number="LOT-26-00003",
        position_id=10,
        production_order_id=20,
        quantity=2.0,
        reason="tool_breakage",
        replacement_lot_id=2,
        replacement_lot_number="LOT-26-00012",
        actor_id=99,
        completion_id=30,
    )

    await handler.execute(event, source_event_id="stream-id-1")

    notified_user_ids = {n.user_id for n in inapp.saved}
    assert notified_user_ids == {manager_a.id, manager_b.id}
    for notification in inapp.saved:
        assert notification.type == NotificationType.PIECES_SCRAPPED
        assert "LOT-26-00012" in notification.message
        assert "LOT-26-00003" in notification.message


async def test_pieces_scrapped_without_replacement_mentions_reason_and_lot() -> None:
    manager = make_user(id=1, permissions=[Permission.MANAGE_LOTS])
    user_repo = FakeUserRepositoryWithPermissions([manager])
    inapp = FakeNotificationRepository()
    handler = HandleEventNotifications(
        inapp, FakeEmailNotificationRepository(), user_repo=user_repo, uow=FakeUnitOfWork()
    )

    event = PiecesScrapped(
        lot_id=1,
        lot_number="LOT-26-00004",
        position_id=10,
        production_order_id=20,
        quantity=1.0,
        reason="operator_error",
        replacement_lot_id=None,
        replacement_lot_number=None,
        actor_id=99,
        completion_id=31,
    )

    await handler.execute(event, source_event_id="stream-id-2")

    assert len(inapp.saved) == 1
    assert "LOT-26-00004" in inapp.saved[0].message
    assert "operator_error" in inapp.saved[0].message
