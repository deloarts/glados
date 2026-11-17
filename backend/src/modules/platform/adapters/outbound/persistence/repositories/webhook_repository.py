"""Concrete implementations of webhook subscription and delivery repositories."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.date_range import day_after_utc
from src.modules.platform.adapters.outbound.persistence.date_range import day_start_utc
from src.modules.platform.adapters.outbound.persistence.models.webhook_model import (
    WebhookDeliveryOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.webhook_model import (
    WebhookSubscriptionOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.tenant_zone import date_filter_zone
from src.modules.platform.domain.entities.webhook_delivery import WebhookDelivery
from src.modules.platform.domain.entities.webhook_subscription import WebhookSubscription
from src.modules.platform.ports.outbound.repositories.webhook_delivery_repository import (
    WebhookDeliveryFilterDto,
)


def _subscription_to_entity(orm: WebhookSubscriptionOrmModel) -> WebhookSubscription:
    return WebhookSubscription(
        id=orm.id,
        public_id=orm.public_id,
        name=orm.name,
        url=orm.url,
        # None only when the stored value could not be decrypted, the
        # dispatcher then records a failed delivery instead of signing.
        secret=orm.secret or "",
        event_types=list(orm.event_types),
        is_active=orm.is_active,
        created=orm.created,
        creator_id=orm.creator_id,
    )


def _delivery_to_entity(orm: WebhookDeliveryOrmModel) -> WebhookDelivery:
    return WebhookDelivery(
        id=orm.id,
        public_id=orm.public_id,
        subscription_id=orm.subscription_id,
        event_type=orm.event_type,
        source_event_id=orm.source_event_id,
        payload=orm.payload,
        attempted_at=orm.attempted_at,
        http_status=orm.http_status,
        duration_ms=orm.duration_ms,
        error=orm.error,
        success=orm.success,
    )


class SqlAlchemyWebhookSubscriptionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_all(self) -> list[WebhookSubscription]:
        rows = await self._db.scalars(
            select(WebhookSubscriptionOrmModel).order_by(WebhookSubscriptionOrmModel.id)
        )
        return [_subscription_to_entity(r) for r in rows]

    async def get_active(self) -> list[WebhookSubscription]:
        rows = await self._db.scalars(
            select(WebhookSubscriptionOrmModel)
            .where(WebhookSubscriptionOrmModel.is_active.is_(True))
            .order_by(WebhookSubscriptionOrmModel.id)
        )
        return [_subscription_to_entity(r) for r in rows]

    async def get_by_id(self, subscription_id: int) -> WebhookSubscription | None:
        orm = await self._db.scalar(by_id(WebhookSubscriptionOrmModel, subscription_id).limit(1))
        return _subscription_to_entity(orm) if orm else None

    async def save(self, subscription: WebhookSubscription) -> WebhookSubscription:
        if subscription.id == 0:
            orm = WebhookSubscriptionOrmModel(
                name=subscription.name,
                url=subscription.url,
                secret=subscription.secret,
                event_types=subscription.event_types,
                is_active=subscription.is_active,
                created=subscription.created,
                creator_id=subscription.creator_id,
            )
            self._db.add(orm)
            await self._db.flush()
            await self._db.refresh(orm)
            return _subscription_to_entity(orm)

        existing = await self._db.scalar(
            select(WebhookSubscriptionOrmModel)
            .where(WebhookSubscriptionOrmModel.id == subscription.id)
            .limit(1)
        )
        if not existing:
            raise ValueError(f"Webhook subscription id={subscription.id} not found.")
        existing.name = subscription.name
        existing.url = subscription.url
        existing.event_types = subscription.event_types
        existing.is_active = subscription.is_active
        await self._db.flush()
        await self._db.refresh(existing)
        return _subscription_to_entity(existing)

    async def delete(self, subscription_id: int) -> None:
        orm = await self._db.scalar(by_id(WebhookSubscriptionOrmModel, subscription_id).limit(1))
        if orm:
            await self._db.delete(orm)
            await self._db.flush()


class SqlAlchemyWebhookDeliveryRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save(self, delivery: WebhookDelivery) -> WebhookDelivery:
        orm = WebhookDeliveryOrmModel(
            subscription_id=delivery.subscription_id,
            event_type=delivery.event_type,
            source_event_id=delivery.source_event_id,
            payload=delivery.payload,
            attempted_at=delivery.attempted_at,
            http_status=delivery.http_status,
            duration_ms=delivery.duration_ms,
            error=delivery.error,
            success=delivery.success,
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return _delivery_to_entity(orm)

    async def get_by_id(self, delivery_id: int) -> WebhookDelivery | None:
        orm = await self._db.scalar(by_id(WebhookDeliveryOrmModel, delivery_id).limit(1))
        return _delivery_to_entity(orm) if orm else None

    async def get_by_subscription_id(
        self,
        subscription_id: int,
        skip: int = 0,
        limit: int = 50,
        filters: WebhookDeliveryFilterDto | None = None,
    ) -> tuple[int, list[WebhookDelivery]]:
        q = select(WebhookDeliveryOrmModel).where(
            WebhookDeliveryOrmModel.subscription_id == subscription_id
        )
        if filters is not None:
            zone = await date_filter_zone(self._db, filters.attempted_from, filters.attempted_to)
            if filters.success is not None:
                q = q.where(WebhookDeliveryOrmModel.success.is_(filters.success))
            if filters.event_type:
                q = q.where(WebhookDeliveryOrmModel.event_type == filters.event_type)
            if filters.attempted_from:
                q = q.where(
                    WebhookDeliveryOrmModel.attempted_at
                    >= day_start_utc(filters.attempted_from, zone)
                )
            if filters.attempted_to:
                q = q.where(
                    WebhookDeliveryOrmModel.attempted_at < day_after_utc(filters.attempted_to, zone)
                )
        total, rows = await fetch_page(
            self._db, q, skip, limit, WebhookDeliveryOrmModel.attempted_at.desc()
        )
        return total, [_delivery_to_entity(r) for r in rows]

    async def get_failed(self, skip: int = 0, limit: int = 50) -> tuple[int, list[WebhookDelivery]]:
        q = select(WebhookDeliveryOrmModel).where(WebhookDeliveryOrmModel.success.is_(False))
        total, rows = await fetch_page(
            self._db, q, skip, limit, WebhookDeliveryOrmModel.attempted_at.desc()
        )
        return total, [_delivery_to_entity(r) for r in rows]

    async def recent_outcomes(
        self, subscription_id: int, limit: int
    ) -> list[tuple[datetime, bool]]:
        rows = await self._db.execute(
            select(WebhookDeliveryOrmModel.attempted_at, WebhookDeliveryOrmModel.success)
            .where(WebhookDeliveryOrmModel.subscription_id == subscription_id)
            .order_by(
                WebhookDeliveryOrmModel.attempted_at.desc(), WebhookDeliveryOrmModel.id.desc()
            )
            .limit(limit)
        )
        return [(attempted_at, success) for attempted_at, success in rows.all()]

    async def exists_success(self, subscription_id: int, source_event_id: str) -> bool:
        return (
            await self._db.scalar(
                select(WebhookDeliveryOrmModel.id)
                .where(
                    WebhookDeliveryOrmModel.subscription_id == subscription_id,
                    WebhookDeliveryOrmModel.source_event_id == source_event_id,
                    WebhookDeliveryOrmModel.success.is_(True),
                )
                .limit(1)
            )
            is not None
        )
