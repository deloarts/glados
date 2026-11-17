"""
Admin webhook management. Reads require read:settings, writes write:settings
(enforced in the use cases). The subscription secret appears exactly once,
in the create response.
"""

from datetime import date

from fastapi import Depends
from fastapi import Query
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.webhooks import (
    get_create_webhook_subscription_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.webhooks import (
    get_delete_webhook_subscription_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.webhooks import (
    get_failed_webhook_deliveries_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.webhooks import (
    get_retry_webhook_delivery_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.webhooks import (
    get_update_webhook_subscription_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.webhooks import get_webhook_deliveries_use_case
from src.modules.platform.adapters.inbound.api.deps.webhooks import (
    get_webhook_subscriptions_use_case,
)
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.adapters.inbound.api.schemas.webhook_schema import (
    CreatedWebhookSubscriptionResult,
)
from src.modules.platform.adapters.inbound.api.schemas.webhook_schema import WebhookDeliveryResult
from src.modules.platform.adapters.inbound.api.schemas.webhook_schema import (
    WebhookSubscriptionCreateRequest,
)
from src.modules.platform.adapters.inbound.api.schemas.webhook_schema import (
    WebhookSubscriptionResult,
)
from src.modules.platform.adapters.inbound.api.schemas.webhook_schema import (
    WebhookSubscriptionUpdateRequest,
)
from src.modules.platform.application.dto.webhook_dto import CreateWebhookSubscriptionCommand
from src.modules.platform.application.dto.webhook_dto import UpdateWebhookSubscriptionCommand
from src.modules.platform.application.use_cases.webhook.get_webhook_deliveries import (
    GetFailedWebhookDeliveries,
)
from src.modules.platform.application.use_cases.webhook.get_webhook_deliveries import (
    GetWebhookDeliveries,
)
from src.modules.platform.application.use_cases.webhook.manage_webhook_subscriptions import (
    CreateWebhookSubscription,
)
from src.modules.platform.application.use_cases.webhook.manage_webhook_subscriptions import (
    DeleteWebhookSubscription,
)
from src.modules.platform.application.use_cases.webhook.manage_webhook_subscriptions import (
    GetWebhookSubscriptions,
)
from src.modules.platform.application.use_cases.webhook.manage_webhook_subscriptions import (
    UpdateWebhookSubscription,
)
from src.modules.platform.application.use_cases.webhook.retry_webhook_delivery import (
    RetryWebhookDelivery,
)
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.events.registry import EVENT_REGISTRY
from src.modules.platform.ports.outbound.repositories.webhook_delivery_repository import (
    WebhookDeliveryFilterDto,
)

router = APIRouter()


@router.get("/event-types", response_model=list[str])
async def read_event_types(_: User = Depends(get_current_active_user)) -> list[str]:
    """All event type names a subscription can listen to (plus "*" for all)."""
    return sorted(EVENT_REGISTRY)


# Deliberately unpaginated: bounded per-instance collection (the webhook
# subscription list).
@router.get("/", response_model=list[WebhookSubscriptionResult])
async def read_webhook_subscriptions(
    actor: User = Depends(get_current_active_user),
    use_case: GetWebhookSubscriptions = Depends(get_webhook_subscriptions_use_case),
) -> list[WebhookSubscriptionResult]:
    return await use_case.execute(actor=actor)


@router.post(
    "/", response_model=CreatedWebhookSubscriptionResult, status_code=status.HTTP_201_CREATED
)
async def create_webhook_subscription(
    body: WebhookSubscriptionCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateWebhookSubscription = Depends(get_create_webhook_subscription_use_case),
) -> CreatedWebhookSubscriptionResult:
    cmd = CreateWebhookSubscriptionCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.put("/{subscription_id}", response_model=WebhookSubscriptionResult)
async def update_webhook_subscription(
    subscription_id: int,
    body: WebhookSubscriptionUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateWebhookSubscription = Depends(get_update_webhook_subscription_use_case),
) -> WebhookSubscriptionResult:
    cmd = UpdateWebhookSubscriptionCommand(**body.model_dump())
    return await use_case.execute(actor=actor, subscription_id=subscription_id, cmd=cmd)


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook_subscription(
    subscription_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteWebhookSubscription = Depends(get_delete_webhook_subscription_use_case),
) -> None:
    await use_case.execute(actor=actor, subscription_id=subscription_id)


@router.get("/deliveries/failed", response_model=PageResponse[WebhookDeliveryResult])
async def read_failed_webhook_deliveries(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
    actor: User = Depends(get_current_active_user),
    use_case: GetFailedWebhookDeliveries = Depends(get_failed_webhook_deliveries_use_case),
) -> PageResponse[WebhookDeliveryResult]:
    """Failed attempts across all subscriptions, newest first. Declared
    before /{subscription_id}/deliveries so the literal path wins."""
    result = await use_case.execute(actor=actor, skip=skip, limit=limit)
    return PageResponse(items=result.items, total=result.total, limit=limit, skip=skip)


@router.get("/{subscription_id}/deliveries", response_model=PageResponse[WebhookDeliveryResult])
async def read_webhook_deliveries(
    subscription_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
    success: bool | None = None,
    event_type: str | None = None,
    attempted_from: date | None = None,
    attempted_to: date | None = None,
    actor: User = Depends(get_current_active_user),
    use_case: GetWebhookDeliveries = Depends(get_webhook_deliveries_use_case),
) -> PageResponse[WebhookDeliveryResult]:
    """One subscription's delivery attempts, newest first, optionally narrowed
    by outcome, exact event type, and an inclusive attempted-at day range."""
    filters = WebhookDeliveryFilterDto(
        success=success,
        event_type=event_type,
        attempted_from=attempted_from,
        attempted_to=attempted_to,
    )
    result = await use_case.execute(
        actor=actor, subscription_id=subscription_id, skip=skip, limit=limit, filters=filters
    )
    return PageResponse(items=result.items, total=result.total, limit=limit, skip=skip)


@router.post("/deliveries/{delivery_id}/retry", response_model=WebhookDeliveryResult)
async def retry_webhook_delivery(
    delivery_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RetryWebhookDelivery = Depends(get_retry_webhook_delivery_use_case),
) -> WebhookDeliveryResult:
    return await use_case.execute(actor=actor, delivery_id=delivery_id)
