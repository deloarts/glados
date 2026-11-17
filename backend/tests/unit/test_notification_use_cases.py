"""
Unit tests for all notification use cases.
No database, no HTTP. All dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.platform.application.use_cases.notification.delete_notification import (
    ClearAllNotifications,
)
from src.modules.platform.application.use_cases.notification.delete_notification import (
    DeleteNotification,
)
from src.modules.platform.application.use_cases.notification.get_notifications import (
    GetNotifications,
)
from src.modules.platform.application.use_cases.notification.mark_notification_read import (
    MarkAllNotificationsRead,
)
from src.modules.platform.application.use_cases.notification.mark_notification_read import (
    MarkNotificationRead,
)
from src.modules.platform.domain.entities.notification import Notification
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import NotificationNotFoundError
from src.modules.platform.domain.value_objects.notification_type import NotificationType
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

# ── Helpers ───────────────────────────────────────────────────────────


def make_notification(
    id: int = 1,
    user_id: int = 1,
    is_read: bool = False,
    title: str = "Test notification",
) -> Notification:
    return Notification(
        id=id,
        user_id=user_id,
        type=NotificationType.DEMAND_ITEM_FULFILLED,
        title=title,
        message="A demand item was created.",
        is_read=is_read,
        created_at=datetime.now(UTC),
    )


class FakeNotificationRepository:
    def __init__(self, notifications: list[Notification] | None = None):
        self._notifications: dict[int, Notification] = {}
        self._next_id = 1
        for n in notifications or []:
            self._notifications[n.id] = n
            self._next_id = max(self._next_id, n.id + 1)
        self._mark_read_calls: list[int] = []
        self._mark_all_read_calls: list[int] = []
        self._deleted_ids: list[int] = []
        self._deleted_user_ids: list[int] = []

    @property
    def mark_all_read_calls(self) -> list[int]:
        """The user id of every mark-all-read call so far, for assertions."""
        return self._mark_all_read_calls

    @property
    def deleted_ids(self) -> list[int]:
        """The ids of the notifications deleted so far, for assertions."""
        return self._deleted_ids

    async def get_by_id(self, notification_id: int) -> Notification | None:
        return self._notifications.get(notification_id)

    async def get_by_user_id(self, user_id: int, unread_only: bool = False) -> list[Notification]:
        items = [n for n in self._notifications.values() if n.user_id == user_id]
        if unread_only:
            items = [n for n in items if not n.is_read]
        return items

    async def get_unread_count(self, user_id: int) -> int:
        return sum(
            1 for n in self._notifications.values() if n.user_id == user_id and not n.is_read
        )

    async def mark_read(self, notification_id: int) -> None:
        self._mark_read_calls.append(notification_id)
        if notification_id in self._notifications:
            self._notifications[notification_id].is_read = True

    async def mark_all_read(self, user_id: int) -> None:
        self._mark_all_read_calls.append(user_id)
        for n in self._notifications.values():
            if n.user_id == user_id:
                n.is_read = True

    async def delete_by_id(self, notification_id: int) -> None:
        self._deleted_ids.append(notification_id)
        self._notifications.pop(notification_id, None)

    async def delete_all_by_user_id(self, user_id: int) -> None:
        self._deleted_user_ids.append(user_id)
        self._notifications = {k: v for k, v in self._notifications.items() if v.user_id != user_id}

    async def save(self, notification: Notification) -> Notification:
        if notification.id == 0:
            notification.id = self._next_id
            self._next_id += 1
        self._notifications[notification.id] = notification
        return notification


# ── GetNotifications ──────────────────────────────────────────────────


class TestGetNotifications:
    def setup_method(self):
        self.user = make_user(id=1)
        self.notifications = [
            make_notification(id=1, user_id=1, is_read=False),
            make_notification(id=2, user_id=1, is_read=True),
            make_notification(id=3, user_id=2, is_read=False),
        ]
        self.repo = FakeNotificationRepository(self.notifications)
        self.use_case = GetNotifications(self.repo)

    async def test_returns_own_notifications_only(self):
        result = await self.use_case.execute(actor=self.user)
        assert result.total == 2

    async def test_returns_unread_count(self):
        result = await self.use_case.execute(actor=self.user)
        assert result.unread_count == 1

    async def test_unread_only_filter(self):
        result = await self.use_case.execute(actor=self.user, unread_only=True)
        assert result.total == 1
        assert all(not item.is_read for item in result.items)

    async def test_all_read_returns_zero_unread(self):
        read_repo = FakeNotificationRepository([make_notification(id=1, user_id=1, is_read=True)])
        result = await GetNotifications(read_repo).execute(actor=self.user)
        assert result.unread_count == 0


# ── MarkNotificationRead ──────────────────────────────────────────────


class TestMarkNotificationRead:
    def setup_method(self):
        self.user = make_user(id=1)
        self.other = make_user(id=2, username="other")
        self.sysuser = make_user(id=3, username="system", is_systemuser=True)
        self.notification = make_notification(id=1, user_id=1)
        self.repo = FakeNotificationRepository([self.notification])
        self.use_case = MarkNotificationRead(self.repo, uow=FakeUnitOfWork())

    async def test_owner_can_mark_read(self):
        await self.use_case.execute(actor=self.user, notification_id=1)
        assert (await self.repo.get_by_id(1)).is_read is True

    async def test_other_user_cannot_mark_read(self):
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=self.other, notification_id=1)

    async def test_systemuser_can_mark_any_notification_read(self):
        await self.use_case.execute(actor=self.sysuser, notification_id=1)
        assert (await self.repo.get_by_id(1)).is_read is True

    async def test_not_found_raises(self):
        with pytest.raises(NotificationNotFoundError):
            await self.use_case.execute(actor=self.user, notification_id=999)


# ── MarkAllNotificationsRead ──────────────────────────────────────────


class TestMarkAllNotificationsRead:
    def setup_method(self):
        self.user = make_user(id=1)
        notifications = [
            make_notification(id=1, user_id=1, is_read=False),
            make_notification(id=2, user_id=1, is_read=False),
        ]
        self.repo = FakeNotificationRepository(notifications)
        self.use_case = MarkAllNotificationsRead(self.repo, uow=FakeUnitOfWork())

    async def test_marks_all_read_for_actor(self):
        await self.use_case.execute(actor=self.user)
        assert 1 in self.repo.mark_all_read_calls

    async def test_all_notifications_become_read(self):
        await self.use_case.execute(actor=self.user)
        unread = [n for n in self.repo._notifications.values() if not n.is_read]
        assert len(unread) == 0


# ── DeleteNotification ────────────────────────────────────────────────


class TestDeleteNotification:
    def setup_method(self):
        self.user = make_user(id=1)
        self.other = make_user(id=2, username="other")
        self.sysuser = make_user(id=3, username="system", is_systemuser=True)
        self.notification = make_notification(id=1, user_id=1)
        self.repo = FakeNotificationRepository([self.notification])
        self.use_case = DeleteNotification(self.repo, uow=FakeUnitOfWork())

    async def test_owner_can_delete(self):
        await self.use_case.execute(actor=self.user, notification_id=1)
        assert 1 in self.repo.deleted_ids

    async def test_other_user_cannot_delete(self):
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=self.other, notification_id=1)

    async def test_systemuser_can_delete_any(self):
        await self.use_case.execute(actor=self.sysuser, notification_id=1)
        assert 1 in self.repo.deleted_ids

    async def test_not_found_raises(self):
        with pytest.raises(NotificationNotFoundError):
            await self.use_case.execute(actor=self.user, notification_id=999)


# ── ClearAllNotifications ─────────────────────────────────────────────


class TestClearAllNotifications:
    def setup_method(self):
        self.user = make_user(id=1)
        notifications = [
            make_notification(id=1, user_id=1),
            make_notification(id=2, user_id=1),
            make_notification(id=3, user_id=2),
        ]
        self.repo = FakeNotificationRepository(notifications)
        self.use_case = ClearAllNotifications(self.repo, uow=FakeUnitOfWork())

    async def test_clears_all_for_actor(self):
        await self.use_case.execute(actor=self.user)
        remaining = [n for n in self.repo._notifications.values() if n.user_id == 1]
        assert len(remaining) == 0

    async def test_does_not_delete_other_users_notifications(self):
        await self.use_case.execute(actor=self.user)
        other_remaining = [n for n in self.repo._notifications.values() if n.user_id == 2]
        assert len(other_remaining) == 1
