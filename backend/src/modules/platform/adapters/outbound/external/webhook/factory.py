"""
Builds the webhook target guard and dispatcher from the deployment config,
so the request path and the event worker refuse the same internal subnets.
"""

from src.modules.platform.adapters.outbound.external.webhook.httpx_webhook_dispatcher import (
    HttpxWebhookDispatcher,
)
from src.modules.platform.adapters.outbound.external.webhook.webhook_target_guard import (
    WebhookTargetGuard,
)
from src.modules.platform.infrastructure.config.settings import cfg


def create_webhook_target_guard() -> WebhookTargetGuard:
    return WebhookTargetGuard(cfg.network.internal_subnets)


def create_webhook_dispatcher() -> HttpxWebhookDispatcher:
    return HttpxWebhookDispatcher(create_webhook_target_guard())
