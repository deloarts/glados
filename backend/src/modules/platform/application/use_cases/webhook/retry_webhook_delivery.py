"""
Manual redelivery of one logged webhook delivery, the admin's "try again"
button. Re-sends the stored payload as-is and appends a new log entry with
the outcome; it never mutates the original entry.
"""

from src.modules.platform.application.dto.webhook_dto import WebhookDeliveryResult
from src.modules.platform.application.mappers.webhook_mapper import WebhookMapper
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.entities.webhook_delivery import WebhookDelivery
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import WebhookDeliveryNotFoundError
from src.modules.platform.domain.exceptions import WebhookSubscriptionNotFoundError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.webhook_delivery_repository import (
    IWebhookDeliveryRepository,
)
from src.modules.platform.ports.outbound.repositories.webhook_subscription_repository import (
    IWebhookSubscriptionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.platform.ports.outbound.webhook_dispatcher_port import IWebhookDispatcher
from src.shared_kernel.domain.services.clock import now_utc


class RetryWebhookDelivery:
    def __init__(
        self,
        subscription_repo: IWebhookSubscriptionRepository,
        delivery_repo: IWebhookDeliveryRepository,
        dispatcher: IWebhookDispatcher,
        settings_repo: IPlatformSettingsRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._subscriptions = subscription_repo
        self._deliveries = delivery_repo
        self._dispatcher = dispatcher
        self._settings = settings_repo
        self._uow = uow

    async def execute(self, actor: User, delivery_id: int) -> WebhookDeliveryResult:
        if not actor.has_permission(Permission.WRITE_SETTINGS):
            raise InsufficientPermissionsError("Retrying a webhook requires write:settings.")

        delivery = found_or_raise(
            await self._deliveries.get_by_id(delivery_id),
            WebhookDeliveryNotFoundError,
            f"Webhook delivery #{delivery_id} not found.",
        )

        subscription = await self._subscriptions.get_by_id(delivery.subscription_id)
        if not subscription:
            raise WebhookSubscriptionNotFoundError(
                f"Webhook subscription #{delivery.subscription_id} no longer exists."
            )

        allow_private = (await self._settings.get_features()).allow_private_webhooks
        # Nothing is pending yet. Ending the read transaction keeps a pooled
        # connection from idling while the receiver answers; the attempt is
        # recorded in its own transaction afterwards.
        await self._uow.commit()
        result = await self._dispatcher.post(
            url=subscription.url,
            secret=subscription.secret,
            event_type=delivery.event_type,
            delivery_id=delivery.source_event_id,
            payload=delivery.payload,
            allow_private=allow_private,
        )
        success = result.http_status is not None and 200 <= result.http_status < 300

        saved = await self._deliveries.save(
            WebhookDelivery(
                id=0,
                subscription_id=subscription.id,
                event_type=delivery.event_type,
                source_event_id=delivery.source_event_id,
                payload=delivery.payload,
                attempted_at=now_utc(),
                http_status=result.http_status,
                duration_ms=result.duration_ms,
                error=result.error,
                success=success,
            )
        )
        await self._uow.commit()

        log.info(
            f"Retried webhook delivery #{delivery_id} to "
            f"{subscription.name!r}: "
            + (f"HTTP {result.http_status}." if result.http_status else f"failed ({result.error}).")
        )
        return WebhookMapper.delivery_to_result(saved)
