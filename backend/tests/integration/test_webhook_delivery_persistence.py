"""
Proves that dispatching an event and retrying a delivery persist their
delivery rows. The dispatch is read back from a fresh session and the retry
through the delivery listing, so a use case that forgets to commit its unit
of work fails here instead of silently losing the attempt. The receiver is
a fake dispatcher, so no request leaves the process.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy import select

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.platform.adapters.inbound.api.deps.services import get_webhook_dispatcher
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.adapters.outbound.persistence.repositories.webhook_repository import (
    SqlAlchemyWebhookDeliveryRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.webhook_repository import (
    SqlAlchemyWebhookSubscriptionRepository,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.use_cases.webhook.dispatch_event_to_webhooks import (
    DispatchEventToWebhooks,
)
from src.modules.platform.domain.entities.admin_settings.features import AdminFeatureSettings
from src.modules.platform.domain.entities.admin_settings.notifications import (
    AdminNotificationSettings,
)
from src.modules.platform.domain.entities.webhook_delivery import WebhookDelivery
from src.modules.platform.domain.entities.webhook_subscription import WebhookSubscription
from src.modules.platform.domain.exceptions import WebhookDeliveryFailedError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.webhook_dispatcher_port import WebhookDispatchResult
from src.modules.workspace.domain.events.project_events import ProjectCreated


class _FakeDispatcher:
    def __init__(self, http_status: int | None) -> None:
        self._http_status = http_status

    async def post(self, **_: Any) -> WebhookDispatchResult:
        error = None if self._http_status else "timeout"
        return WebhookDispatchResult(self._http_status, 5, error)


async def _seed_features(db: Any) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_features(
        AdminFeatureSettings(
            id=1,
            enable_email_notifications=True,
            enable_production_planning=True,
            allow_private_webhooks=True,
        )
    )


async def _subscription_id(db: Any) -> int:
    creator = await db.scalar(select(UserOrmModel).limit(1))
    saved = await SqlAlchemyWebhookSubscriptionRepository(db).save(
        WebhookSubscription(
            id=0,
            name="Hook",
            url="https://example.com/hook",
            secret="s3cret",
            event_types=["*"],
            is_active=True,
            created=datetime.now(UTC),
            creator_id=creator.id,
        )
    )
    await db.commit()
    return saved.id


async def _deliveries(subscription_id: int) -> list[WebhookDelivery]:
    async with SessionLocal() as fresh:
        _, rows = await SqlAlchemyWebhookDeliveryRepository(fresh).get_by_subscription_id(
            subscription_id
        )
    return list(rows)


@pytest.mark.parametrize(("http_status", "success"), [(204, True), (None, False)])
async def test_a_dispatch_persists_its_delivery_row(
    db, create_user, http_status: int | None, success: bool
) -> None:
    await create_user()
    await SqlAlchemyAdminSettingsRepository(db).save_notifications(
        AdminNotificationSettings(id=1, webhook_timeout_seconds=10)
    )
    await _seed_features(db)
    subscription_id = await _subscription_id(db)
    use_case = DispatchEventToWebhooks(
        SqlAlchemyWebhookSubscriptionRepository(db),
        SqlAlchemyWebhookDeliveryRepository(db),
        _FakeDispatcher(http_status),
        settings_repo=SqlAlchemyAdminSettingsRepository(db),
        uow=SqlAlchemyUnitOfWork(db),
    )
    event = ProjectCreated(project_id=1, project_number="P-1", actor_id=1, designated_user_id=1)

    if success:
        await use_case.execute(event, "1-0")
    else:
        with pytest.raises(WebhookDeliveryFailedError):
            await use_case.execute(event, "1-0")

    assert [d.success for d in await _deliveries(subscription_id)] == [success]


@pytest.fixture
def accepting_dispatcher():
    app.dependency_overrides[get_webhook_dispatcher] = lambda: _FakeDispatcher(200)
    yield
    app.dependency_overrides.pop(get_webhook_dispatcher, None)


async def test_a_retry_persists_its_new_attempt(db, auth_client, accepting_dispatcher) -> None:
    client = await auth_client(permissions=[Permission.WRITE_SETTINGS, Permission.READ_SETTINGS])
    await _seed_features(db)
    subscription_id = await _subscription_id(db)
    failed = await SqlAlchemyWebhookDeliveryRepository(db).save(
        WebhookDelivery(
            id=0,
            subscription_id=subscription_id,
            event_type="ProjectCreated",
            source_event_id="1-0",
            payload="{}",
            attempted_at=datetime.now(UTC),
            http_status=500,
            duration_ms=5,
            error="HTTP 500",
            success=False,
        )
    )
    await db.commit()

    response = await client.post(f"/api/v1/web/admin/webhooks/deliveries/{failed.id}/retry")

    assert response.status_code == 200, response.text
    listed = await client.get(f"/api/v1/web/admin/webhooks/{subscription_id}/deliveries")
    assert listed.status_code == 200, listed.text
    assert sorted(d["success"] for d in listed.json()["items"]) == [False, True]
