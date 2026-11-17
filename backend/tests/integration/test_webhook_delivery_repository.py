"""
The delivery-log query behind the webhook dispatch circuit breaker.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

from sqlalchemy import select

from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.adapters.outbound.persistence.repositories.webhook_repository import (
    SqlAlchemyWebhookDeliveryRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.webhook_repository import (
    SqlAlchemyWebhookSubscriptionRepository,
)
from src.modules.platform.domain.entities.webhook_delivery import WebhookDelivery
from src.modules.platform.domain.entities.webhook_subscription import WebhookSubscription

_START = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)


async def _subscription(db, name: str) -> int:
    creator = await db.scalar(select(UserOrmModel).limit(1))
    saved = await SqlAlchemyWebhookSubscriptionRepository(db).save(
        WebhookSubscription(
            id=0,
            name=name,
            url=f"https://example.com/{name}",
            secret="s3cret",
            event_types=["*"],
            is_active=True,
            created=_START,
            creator_id=creator.id,
        )
    )
    return saved.id


async def test_recent_outcomes_returns_the_newest_attempts_of_one_subscription(
    db, create_user
) -> None:
    await create_user()
    hook = await _subscription(db, "hook")
    other = await _subscription(db, "other")
    repo = SqlAlchemyWebhookDeliveryRepository(db)
    for minute, (subscription_id, success) in enumerate(
        [(hook, True), (hook, False), (other, True), (hook, False), (hook, True)]
    ):
        await repo.save(
            WebhookDelivery(
                id=0,
                subscription_id=subscription_id,
                event_type="ProjectCreated",
                source_event_id=f"1-{minute}",
                payload="{}",
                attempted_at=_START + timedelta(minutes=minute),
                http_status=200 if success else 500,
                duration_ms=10,
                error=None if success else "HTTP 500",
                success=success,
            )
        )

    outcomes = await repo.recent_outcomes(hook, 3)

    assert [success for _, success in outcomes] == [True, False, False]
    assert outcomes[0][0].replace(tzinfo=UTC) == _START + timedelta(minutes=4)
