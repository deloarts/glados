"""Use cases for retrieving webhook subscription delivery history and retry management."""

from src.modules.platform.application.dto.webhook_dto import WebhookDeliveriesResult
from src.modules.platform.application.mappers.webhook_mapper import WebhookMapper
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import WebhookSubscriptionNotFoundError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.repositories.webhook_delivery_repository import (
    IWebhookDeliveryRepository,
)
from src.modules.platform.ports.outbound.repositories.webhook_delivery_repository import (
    WebhookDeliveryFilterDto,
)
from src.modules.platform.ports.outbound.repositories.webhook_subscription_repository import (
    IWebhookSubscriptionRepository,
)


class GetWebhookDeliveries:
    def __init__(
        self,
        subscription_repo: IWebhookSubscriptionRepository,
        delivery_repo: IWebhookDeliveryRepository,
    ) -> None:
        self._subscriptions = subscription_repo
        self._deliveries = delivery_repo

    async def execute(
        self,
        actor: User,
        subscription_id: int,
        skip: int = 0,
        limit: int = 50,
        filters: WebhookDeliveryFilterDto | None = None,
    ) -> WebhookDeliveriesResult:
        if not actor.has_permission(Permission.READ_SETTINGS):
            raise InsufficientPermissionsError("Reading webhook deliveries requires read:settings.")

        if not await self._subscriptions.get_by_id(subscription_id):
            raise WebhookSubscriptionNotFoundError(
                f"Webhook subscription #{subscription_id} not found."
            )

        total, items = await self._deliveries.get_by_subscription_id(
            subscription_id, skip, limit, filters
        )
        return WebhookDeliveriesResult(
            total=total, items=[WebhookMapper.delivery_to_result(d) for d in items]
        )


class GetFailedWebhookDeliveries:
    """Cross-subscription view of failed attempts, newest first.

    A message the event worker gives up on after _MAX_DELIVERIES is logged
    and dropped, but for the `webhooks` group every attempt it made is
    already durable in webhook_delivery_table and replayable through
    RetryWebhookDelivery. Nothing surfaced those rows unless the operator
    already knew which subscription to look at, which is exactly what they
    do not know after an endpoint outage. This is that entry point, a read
    over webhook_delivery_table as it stands.
    """

    def __init__(self, delivery_repo: IWebhookDeliveryRepository) -> None:
        self._deliveries = delivery_repo

    async def execute(self, actor: User, skip: int = 0, limit: int = 50) -> WebhookDeliveriesResult:
        if not actor.has_permission(Permission.READ_SETTINGS):
            raise InsufficientPermissionsError("Reading webhook deliveries requires read:settings.")

        total, items = await self._deliveries.get_failed(skip, limit)
        return WebhookDeliveriesResult(
            total=total, items=[WebhookMapper.delivery_to_result(d) for d in items]
        )
