"""
Proves that the two notification background jobs persist what they write.
The event handler is driven through main.py's own worker entry point and
its rows are read back through the API or a fresh session; the digest
sender runs on its own session and the drained queue is checked from
another one. A job that forgets to commit its unit of work fails here
instead of silently losing the rows when its session closes.
"""

from typing import Any

import httpx
import pytest

import src.bootstrap.main as main_module
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.domain.events.bought_item_events import DemandItemStatusChanged
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.platform.adapters.outbound.persistence.repositories.email_notification_repository import (
    SqlAlchemyEmailNotificationRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.use_cases.mail.send_pending_notifications import (
    SendPendingNotifications,
)
from src.modules.platform.domain.entities.email_notification import EmailNotification
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.events.user_events import UserForcedLogout

from .conftest import auth_headers


class _MailOffSettingsRepository(SqlAlchemyAdminSettingsRepository):
    """The real settings repository, except that mail settings (which this
    suite does not seed) read as absent. The events used here never send a
    system mail, so only the mail service construction needs it."""

    async def get_mail(self) -> Any:
        return None


@pytest.fixture(autouse=True)
def _no_mail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main_module, "SqlAlchemyAdminSettingsRepository", _MailOffSettingsRepository
    )
    monkeypatch.setattr(main_module, "SmtpMailService", lambda settings, settings_repo=None: None)


async def test_event_handler_commits_the_in_app_notification(
    client: httpx.AsyncClient, create_user
) -> None:
    user: User = await create_user()

    await main_module._handle_notification_event(
        UserForcedLogout(user_id=user.id, actor_id=1), "1700000000000-0"
    )

    client.headers.update(await auth_headers(user))
    listed = (await client.get("/api/v1/web/notifications/")).json()
    assert listed["total"] == 1
    assert listed["items"][0]["type"] == "forced_logout"


async def test_event_handler_commits_the_email_digest_entry(create_user) -> None:
    user: User = await create_user()

    await main_module._handle_notification_event(
        DemandItemStatusChanged(
            demand_id=11,
            item_article_name="Bolt",
            old_status=BoughtItemDemandStatus.ORDERED,
            new_status=BoughtItemDemandStatus.FULFILLED,
            actor_id=1,
            notify_on_delivery=True,
            creator_id=user.id,
            order_item_id=21,
        ),
        "1700000000001-0",
    )

    async with SessionLocal() as fresh:
        queued = await SqlAlchemyEmailNotificationRepository(fresh).get_by_receiver_id(user.id)
    assert [(e.reason, e.demand_item_id, e.order_item_id) for e in queued] == [
        ("delivered", 11, 21)
    ]


class _EnabledSettings:
    """Admin settings with email notifications and mail switched on, the
    two gates SendPendingNotifications checks before draining the queue."""

    class _On:
        enable_email_notifications = True
        enabled = True

    async def get_features(self) -> Any:
        return self._On()

    async def get_mail(self) -> Any:
        return self._On()


class _RecordingMailService:
    def __init__(self) -> None:
        self.digests: list[str] = []

    async def send_notification_digest(self, *, to: str, **_: Any) -> None:
        self.digests.append(to)


async def test_digest_sender_commits_the_drained_queue(create_user) -> None:
    user: User = await create_user()
    async with SessionLocal() as seed:
        await SqlAlchemyEmailNotificationRepository(seed).save(
            EmailNotification(
                id=0, reason="delivered", receiver_id=user.id, demand_item_id=3, order_item_id=None
            )
        )
        await seed.commit()

    mail = _RecordingMailService()
    async with SessionLocal() as db:
        sent = await SendPendingNotifications(
            notification_repo=SqlAlchemyEmailNotificationRepository(db),
            user_repo=SqlAlchemyUserRepository(db),
            mail_service=mail,  # type: ignore[arg-type]
            admin_settings_repo=_EnabledSettings(),  # type: ignore[arg-type]
            uow=SqlAlchemyUnitOfWork(db),
        ).execute()
    assert sent == 1
    assert mail.digests == [user.email]

    async with SessionLocal() as fresh:
        assert await SqlAlchemyEmailNotificationRepository(fresh).get_by_receiver_id(user.id) == []
