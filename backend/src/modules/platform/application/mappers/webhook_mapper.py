"""Converts between WebhookSubscription/WebhookDelivery domain entities and DTOs."""

from src.modules.platform.application.dto.webhook_dto import CreatedWebhookSubscriptionResult
from src.modules.platform.application.dto.webhook_dto import WebhookDeliveryResult
from src.modules.platform.application.dto.webhook_dto import WebhookSubscriptionResult
from src.modules.platform.domain.entities.webhook_delivery import WebhookDelivery
from src.modules.platform.domain.entities.webhook_subscription import WebhookSubscription


class WebhookMapper:
    @staticmethod
    def to_result(subscription: WebhookSubscription) -> WebhookSubscriptionResult:
        return WebhookSubscriptionResult(
            id=subscription.id,
            public_id=subscription.public_id,
            name=subscription.name,
            url=subscription.url,
            event_types=subscription.event_types,
            is_active=subscription.is_active,
            created=subscription.created,
            creator_id=subscription.creator_id,
        )

    @staticmethod
    def to_created_result(subscription: WebhookSubscription) -> CreatedWebhookSubscriptionResult:
        return CreatedWebhookSubscriptionResult(
            id=subscription.id,
            public_id=subscription.public_id,
            name=subscription.name,
            url=subscription.url,
            event_types=subscription.event_types,
            is_active=subscription.is_active,
            created=subscription.created,
            creator_id=subscription.creator_id,
            secret=subscription.secret,
        )

    @staticmethod
    def delivery_to_result(delivery: WebhookDelivery) -> WebhookDeliveryResult:
        return WebhookDeliveryResult(
            id=delivery.id,
            public_id=delivery.public_id,
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
