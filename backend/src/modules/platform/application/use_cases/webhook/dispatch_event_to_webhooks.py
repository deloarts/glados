"""Fans one domain event out to every active, matching webhook subscription.
Invoked by the event bus worker for each message in the "webhooks" consumer
group.

Delivery semantics: every attempt is logged. If any subscriber fails, a
WebhookDeliveryFailedError is raised so the worker keeps the message pending
and redelivers it, subscribers that already succeeded are skipped on the
retry via the delivery log (exists_success), so nobody gets the event twice.

Fan-out is concurrent, in three deliberate phases (plan / dispatch / record),
so one subscriber hanging until the timeout cannot delay the others or later
messages, since the worker awaits one handler at a time. Only the HTTP posts
run concurrently: the
handler shares one AsyncSession (see main.py's _handle_webhook_event), which
must never see two operations at once, so both DB phases run sequentially.
The read transaction is ended before the posts, so no connection is held
while subscribers take up to the full timeout to answer.

Per-subscriber circuit breaker: when a subscription's last
_BREAKER_FAILURE_THRESHOLD attempts all failed and the newest is younger than
_BREAKER_COOLDOWN, its post is skipped instead of waiting out the timeout
against an endpoint that is known to be down. A skipped subscriber still
counts as failed, so the message stays pending and is redelivered (or
dead-lettered) like any other failure, and no event is silently lost. Skips
write no delivery row, so the cooldown runs from the last real attempt; once
it passes, the next message probes the endpoint with one real post, which
closes the circuit on success or restarts the cooldown on failure. The worker
redelivers no sooner than a minute later, so every redelivery of a message is
a real probe and the breaker only short-circuits the newer messages queued
behind it.
"""

import asyncio
import dataclasses
import json
from datetime import date
from datetime import datetime
from datetime import timedelta
from enum import Enum
from typing import Any

from src.modules.platform.domain.entities.webhook_delivery import WebhookDelivery
from src.modules.platform.domain.entities.webhook_subscription import WebhookSubscription
from src.modules.platform.domain.exceptions import WebhookDeliveryFailedError
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
from src.modules.platform.ports.outbound.webhook_dispatcher_port import WebhookDispatchResult
from src.shared_kernel.domain.events.base import DomainEvent
from src.shared_kernel.domain.services.clock import now_utc

# Worst-case wall time per message drops from 10s x n to 10s x ceil(n/8),
# which for any realistic subscriber count stays well under the worker's
# _MIN_IDLE_MS reclaim threshold. A module constant, not a setting: this is
# a property of the dispatch design, not something an operator should tune.
_MAX_CONCURRENT_POSTS = 8

_BREAKER_FAILURE_THRESHOLD = 5
_BREAKER_COOLDOWN = timedelta(seconds=60)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, date | datetime):
        return obj.isoformat()
    raise TypeError(f"{type(obj).__name__} is not JSON-serializable.")


class DispatchEventToWebhooks:
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

    async def execute(self, event: DomainEvent, source_event_id: str) -> None:
        event_type = type(event).__name__
        subscriptions = [s for s in await self._subscriptions.get_active() if s.matches(event_type)]
        if not subscriptions:
            return

        payload = json.dumps(
            {
                "id": source_event_id,
                "event": event_type,
                "data": dataclasses.asdict(event),
            },
            default=_json_default,
        )

        # Phase 1, plan (sequential, DB): the idempotency guard. Each check is
        # scoped to its own subscription, so running them all first is safe.
        pending = [
            s
            for s in subscriptions
            if not await self._deliveries.exists_success(s.id, source_event_id)
        ]
        if not pending:
            return

        now = now_utc()
        open_circuit = [s for s in pending if await self._circuit_open(s.id, now)]
        for subscription in open_circuit:
            log.warning(
                "Webhook delivery of %s to %r skipped: its last %d attempts failed, "
                "the circuit is open until the cooldown passes.",
                event_type,
                subscription.name,
                _BREAKER_FAILURE_THRESHOLD,
            )
        to_post = [s for s in pending if s not in open_circuit]
        timeout_seconds = (await self._settings.get_notifications()).webhook_timeout_seconds
        allow_private = (await self._settings.get_features()).allow_private_webhooks
        # Nothing is pending yet. Ending the read transaction keeps a pooled
        # connection from idling while slow receivers answer.
        await self._uow.commit()

        # Phase 2, dispatch (concurrent HTTP posts, no DB).
        results = await self._post_concurrently(
            to_post, event_type, source_event_id, payload, timeout_seconds, allow_private
        )

        # Phase 3, record (sequential, DB), in the original subscription
        # order so the delivery log stays deterministic even though the HTTP
        # calls completed in whatever order the endpoints answered.
        failed = [s.name for s in open_circuit]
        for subscription, result in results:
            success = result.http_status is not None and 200 <= result.http_status < 300

            await self._deliveries.save(
                WebhookDelivery(
                    id=0,
                    subscription_id=subscription.id,
                    event_type=event_type,
                    source_event_id=source_event_id,
                    payload=payload,
                    attempted_at=now_utc(),
                    http_status=result.http_status,
                    duration_ms=result.duration_ms,
                    error=result.error,
                    success=success,
                )
            )

            if not success:
                failed.append(subscription.name)
                log.warning(
                    "Webhook delivery of %s to %r failed: %s.",
                    event_type,
                    subscription.name,
                    f"HTTP {result.http_status}" if result.http_status else result.error,
                )

        # Committed before a failure is raised, so a redelivered message finds
        # the successful rows and the idempotency guard skips them.
        await self._uow.commit()

        if failed:
            raise WebhookDeliveryFailedError(
                f"{event_type} not accepted by subscription(s): {', '.join(failed)}."
            )

    async def _circuit_open(self, subscription_id: int, now: datetime) -> bool:
        outcomes = await self._deliveries.recent_outcomes(
            subscription_id, _BREAKER_FAILURE_THRESHOLD
        )
        return (
            len(outcomes) == _BREAKER_FAILURE_THRESHOLD
            and not any(success for _, success in outcomes)
            and now - outcomes[0][0] < _BREAKER_COOLDOWN
        )

    async def _post_concurrently(
        self,
        pending: list[WebhookSubscription],
        event_type: str,
        source_event_id: str,
        payload: str,
        timeout_seconds: int,
        allow_private: bool,
    ) -> list[tuple[WebhookSubscription, WebhookDispatchResult]]:
        """Posts to every pending subscriber, at most _MAX_CONCURRENT_POSTS at
        a time, and returns the results in input order. Nothing here touches
        the session. An exception from `post`, which should never raise, is
        propagated rather than recorded as a phantom success.
        """
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT_POSTS)

        async def _post(subscription: WebhookSubscription) -> WebhookDispatchResult:
            async with semaphore:
                return await self._dispatcher.post(
                    url=subscription.url,
                    secret=subscription.secret,
                    event_type=event_type,
                    delivery_id=source_event_id,
                    payload=payload,
                    allow_private=allow_private,
                    timeout_seconds=timeout_seconds,
                )

        results = await asyncio.gather(*(_post(subscription) for subscription in pending))
        return list(zip(pending, results, strict=True))
