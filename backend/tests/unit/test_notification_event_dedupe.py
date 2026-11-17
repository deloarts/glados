"""
A notification is unique per event and user. The repository inserts with ON
CONFLICT DO NOTHING on that pair against a real SQLite session, since the
claim is about the database; the handler rolls back and sends nothing when a
concurrent delivery of the same event already wrote its notifications.
"""

import importlib

import pytest
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from src.modules.platform.adapters.outbound.persistence.alembic_imports import model_module_names
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.notification_model import (
    NotificationOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.repositories.notification_repository import (
    SqlAlchemyNotificationRepository,
)
from src.modules.platform.application.use_cases.notification.handle_event_notifications import (
    HandleEventNotifications,
)
from src.modules.platform.domain.entities.notification import make_notification
from src.modules.platform.domain.events.user_events import UserPermissionsChanged
from src.modules.platform.domain.value_objects.notification_type import NotificationType
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.test_event_notification_handler import FakeAdminSettingsRepoForEvents
from tests.unit.test_event_notification_handler import FakeEmailNotificationRepository
from tests.unit.test_event_notification_handler import FakeMailServiceForEvents
from tests.unit.test_event_notification_handler import FakeUserRepositoryForEvents
from tests.unit.test_event_notification_handler import make_user

# The mappers resolve every relationship on first use, so every model must be
# imported, not only the notification table this file creates.
for _module_name in model_module_names():
    importlib.import_module(_module_name)


def _notification(user_id: int, source_event_id: str | None):
    return make_notification(
        user_id=user_id,
        type=NotificationType.FORCED_LOGOUT,
        title="Logged out by administrator",
        message="You have been logged out by an administrator.",
        source_event_id=source_event_id,
    )


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[NotificationOrmModel.__table__])
    try:
        yield async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        await engine.dispose()


async def _count(session_factory) -> int:
    async with session_factory() as db:
        return int(await db.scalar(select(func.count()).select_from(NotificationOrmModel)))


async def test_a_second_insert_for_the_same_event_and_user_inserts_nothing(session_factory):
    async with session_factory() as db:
        repo = SqlAlchemyNotificationRepository(db)
        assert await repo.add_for_event(_notification(4, "evt-1")) is True
        assert await repo.add_for_event(_notification(4, "evt-1")) is False
        assert await repo.add_for_event(_notification(5, "evt-1")) is True
        assert await repo.exists_by_source_event_id("evt-1")
        await db.commit()

    assert await _count(session_factory) == 2


async def test_rows_without_an_event_id_never_conflict(session_factory):
    async with session_factory() as db:
        repo = SqlAlchemyNotificationRepository(db)
        assert await repo.add_for_event(_notification(4, None)) is True
        assert await repo.add_for_event(_notification(4, None)) is True
        await db.commit()

    assert await _count(session_factory) == 2


class _ConcurrentlyHandledRepository:
    """The existence check ran before the other delivery committed, and the
    insert then met its row."""

    def __init__(self) -> None:
        self.saved: list = []

    async def exists_by_source_event_id(self, source_event_id: str) -> bool:
        return False

    async def add_for_event(self, notification) -> bool:
        return False


async def test_a_concurrent_delivery_rolls_back_and_sends_no_mail():
    mail = FakeMailServiceForEvents()
    uow = FakeUnitOfWork()
    handler = HandleEventNotifications(
        _ConcurrentlyHandledRepository(),
        FakeEmailNotificationRepository(),
        user_repo=FakeUserRepositoryForEvents({4: make_user(id=4)}),
        mail_service=mail,
        admin_settings_repo=FakeAdminSettingsRepoForEvents(),
        uow=uow,
    )

    await handler.execute(UserPermissionsChanged(user_id=4, actor_id=1), "evt-1")

    assert uow.rollbacks == 1
    assert uow.commits == 0
    assert mail.sent == []
