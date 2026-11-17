"""Use case factories: webhook subscriptions and their deliveries."""

from fastapi import Depends

from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_platform_settings_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_webhook_delivery_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import (
    get_webhook_subscription_repo,
)
from src.modules.platform.adapters.inbound.api.deps.services import get_webhook_dispatcher
from src.modules.platform.adapters.inbound.api.deps.services import get_webhook_target_guard
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
from src.modules.platform.infrastructure.events.registry import EVENT_REGISTRY
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
from src.modules.platform.ports.outbound.webhook_target_guard_port import IWebhookTargetGuard


def get_webhook_subscriptions_use_case(
    subscription_repo: IWebhookSubscriptionRepository = Depends(get_webhook_subscription_repo),
) -> GetWebhookSubscriptions:
    return GetWebhookSubscriptions(subscription_repo)


def get_create_webhook_subscription_use_case(
    subscription_repo: IWebhookSubscriptionRepository = Depends(get_webhook_subscription_repo),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    target_guard: IWebhookTargetGuard = Depends(get_webhook_target_guard),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateWebhookSubscription:
    return CreateWebhookSubscription(
        subscription_repo,
        settings_repo,
        known_event_types=set(EVENT_REGISTRY),
        target_guard=target_guard,
        uow=uow,
    )


def get_update_webhook_subscription_use_case(
    subscription_repo: IWebhookSubscriptionRepository = Depends(get_webhook_subscription_repo),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    target_guard: IWebhookTargetGuard = Depends(get_webhook_target_guard),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateWebhookSubscription:
    return UpdateWebhookSubscription(
        subscription_repo,
        settings_repo,
        known_event_types=set(EVENT_REGISTRY),
        target_guard=target_guard,
        uow=uow,
    )


def get_delete_webhook_subscription_use_case(
    subscription_repo: IWebhookSubscriptionRepository = Depends(get_webhook_subscription_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DeleteWebhookSubscription:
    return DeleteWebhookSubscription(subscription_repo, uow=uow)


def get_failed_webhook_deliveries_use_case(
    delivery_repo: IWebhookDeliveryRepository = Depends(get_webhook_delivery_repo),
) -> GetFailedWebhookDeliveries:
    return GetFailedWebhookDeliveries(delivery_repo)


def get_webhook_deliveries_use_case(
    subscription_repo: IWebhookSubscriptionRepository = Depends(get_webhook_subscription_repo),
    delivery_repo: IWebhookDeliveryRepository = Depends(get_webhook_delivery_repo),
) -> GetWebhookDeliveries:
    return GetWebhookDeliveries(subscription_repo, delivery_repo)


def get_retry_webhook_delivery_use_case(
    subscription_repo: IWebhookSubscriptionRepository = Depends(get_webhook_subscription_repo),
    delivery_repo: IWebhookDeliveryRepository = Depends(get_webhook_delivery_repo),
    dispatcher: IWebhookDispatcher = Depends(get_webhook_dispatcher),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RetryWebhookDelivery:
    return RetryWebhookDelivery(
        subscription_repo, delivery_repo, dispatcher, settings_repo, uow=uow
    )
