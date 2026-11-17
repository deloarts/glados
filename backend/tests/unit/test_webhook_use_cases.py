"""
Unit tests for webhook subscription management, event dispatch (fan-out,
HMAC-signed delivery via the dispatcher port, delivery log, retry-safe
idempotency), and manual redelivery.
"""

import asyncio
import base64
import json
import time
from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest

from src.modules.platform.adapters.outbound.external.webhook.webhook_target_guard import (
    WebhookTargetGuard,
)
from src.modules.platform.application.dto.webhook_dto import CreateWebhookSubscriptionCommand
from src.modules.platform.application.dto.webhook_dto import UpdateWebhookSubscriptionCommand
from src.modules.platform.application.use_cases.webhook.dispatch_event_to_webhooks import (
    DispatchEventToWebhooks,
)
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
from src.modules.platform.domain.entities.admin_settings.features import AdminFeatureSettings
from src.modules.platform.domain.entities.admin_settings.notifications import (
    AdminNotificationSettings,
)
from src.modules.platform.domain.entities.webhook_delivery import WebhookDelivery
from src.modules.platform.domain.entities.webhook_subscription import WebhookSubscription
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import InvalidWebhookConfigurationError
from src.modules.platform.domain.exceptions import WebhookDeliveryFailedError
from src.modules.platform.domain.exceptions import WebhookSubscriptionNotFoundError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.webhook_dispatcher_port import WebhookDispatchResult
from src.modules.workspace.domain.events.project_events import ProjectCreated
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

KNOWN_EVENT_TYPES = {"ProjectCreated", "OrderSubmitted"}


async def _resolve_example_hosts(host: str, port: int) -> list[str]:
    """Every *.example.com host resolves to one public address, anything
    else does not resolve, so no test depends on real DNS."""
    if host.endswith(".example.com"):
        return ["93.184.215.14"]
    raise OSError(f"{host} does not resolve")


GUARD = WebhookTargetGuard((), resolver=_resolve_example_hosts)

# ── Fakes and helpers ─────────────────────────────────────────────────


def make_subscription(id: int = 1, **kwargs) -> WebhookSubscription:
    defaults = dict(
        name=f"Hook {id}",
        url="https://receiver.example.com/hook",
        secret="s3cr3t",
        event_types=["ProjectCreated"],
        is_active=True,
        created=datetime.now(UTC),
        creator_id=1,
    )
    defaults.update(kwargs)
    return WebhookSubscription(id=id, **defaults)


class FakeSubscriptionRepository:
    def __init__(self, subscriptions: list[WebhookSubscription] | None = None):
        self._subs = {s.id: s for s in (subscriptions or [])}
        self._next_id = max(self._subs, default=0) + 1

    async def get_all(self):
        return list(self._subs.values())

    async def get_active(self):
        return [s for s in self._subs.values() if s.is_active]

    async def get_by_id(self, subscription_id):
        return self._subs.get(subscription_id)

    async def save(self, subscription):
        if subscription.id == 0:
            subscription.id = self._next_id
            self._next_id += 1
        self._subs[subscription.id] = subscription
        return subscription

    async def delete(self, subscription_id):
        self._subs.pop(subscription_id, None)


class FakeAdminSettingsRepository:
    def __init__(self, allow_private_webhooks: bool = False, webhook_timeout_seconds: int = 10):
        self._features = AdminFeatureSettings(
            id=1,
            enable_email_notifications=True,
            enable_production_planning=True,
            allow_private_webhooks=allow_private_webhooks,
        )
        self._notifications = AdminNotificationSettings(
            id=1,
            webhook_timeout_seconds=webhook_timeout_seconds,
        )

    async def get_features(self) -> AdminFeatureSettings:
        return self._features

    async def get_notifications(self) -> AdminNotificationSettings:
        return self._notifications


class FakeDeliveryRepository:
    def __init__(self):
        self.saved = []
        self._next_id = 1

    async def save(self, delivery):
        delivery.id = self._next_id
        self._next_id += 1
        self.saved.append(delivery)
        return delivery

    async def get_by_id(self, delivery_id):
        return next((d for d in self.saved if d.id == delivery_id), None)

    async def get_by_subscription_id(self, subscription_id, skip=0, limit=50):
        items = [d for d in self.saved if d.subscription_id == subscription_id]
        return len(items), items[skip : skip + limit]

    async def get_failed(self, skip=0, limit=50):
        items = sorted(
            (d for d in self.saved if not d.success),
            key=lambda d: d.attempted_at,
            reverse=True,
        )
        return len(items), items[skip : skip + limit]

    async def recent_outcomes(self, subscription_id, limit):
        items = [d for d in self.saved if d.subscription_id == subscription_id]
        items.sort(key=lambda d: (d.attempted_at, d.id), reverse=True)
        return [(d.attempted_at, d.success) for d in items[:limit]]

    async def exists_success(self, subscription_id, source_event_id):
        return any(
            d.subscription_id == subscription_id
            and d.source_event_id == source_event_id
            and d.success
            for d in self.saved
        )


class FakeDispatcher:
    """Scripted per-URL results; records every call.

    `delay_seconds` makes a call wait on the event loop, which is how the
    concurrency tests tell parallel fan-out from a serialised loop.
    `in_flight` counts posts currently awaiting and `max_in_flight` the
    peak, so a test can see whether posts overlapped. Ordering of `calls`
    is deliberately not relied on.
    """

    def __init__(
        self,
        results: dict[str, WebhookDispatchResult] | None = None,
        delay_seconds: float = 0.0,
    ):
        self._results = results or {}
        self._delay_seconds = delay_seconds
        self.calls = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def post(
        self, *, url, secret, event_type, delivery_id, payload, allow_private, timeout_seconds=None
    ):
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            if self._delay_seconds:
                await asyncio.sleep(self._delay_seconds)
            self.calls.append(
                {
                    "url": url,
                    "secret": secret,
                    "event_type": event_type,
                    "delivery_id": delivery_id,
                    "payload": payload,
                    "allow_private": allow_private,
                    "timeout_seconds": timeout_seconds,
                }
            )
            return self._results.get(
                url, WebhookDispatchResult(http_status=200, duration_ms=5, error=None)
            )
        finally:
            self.in_flight -= 1


ADMIN = None
READER = None


def setup_module():
    global ADMIN, READER
    ADMIN = make_user(id=1, permissions=[Permission.READ_SETTINGS, Permission.WRITE_SETTINGS])
    READER = make_user(id=2, permissions=[Permission.READ_SETTINGS])


# ── Subscription CRUD ─────────────────────────────────────────────────


async def test_create_generates_secret_and_returns_it_once():
    repo = FakeSubscriptionRepository()
    result = await CreateWebhookSubscription(
        repo,
        FakeAdminSettingsRepository(),
        known_event_types=KNOWN_EVENT_TYPES,
        target_guard=GUARD,
        uow=FakeUnitOfWork(),
    ).execute(
        actor=ADMIN,
        cmd=CreateWebhookSubscriptionCommand(
            name="ERP", url="https://erp.example.com/hook", event_types=["ProjectCreated"]
        ),
    )
    assert result.secret.startswith("whsec_")  # Standard Webhooks secret format
    assert len(base64.b64decode(result.secret.removeprefix("whsec_"))) == 32
    assert result.id > 0

    listed = await GetWebhookSubscriptions(repo).execute(actor=READER)
    assert not hasattr(listed[0], "secret")  # list view never exposes it


async def test_create_requires_write_settings():
    with pytest.raises(InsufficientPermissionsError):
        await CreateWebhookSubscription(
            FakeSubscriptionRepository(),
            FakeAdminSettingsRepository(),
            known_event_types=KNOWN_EVENT_TYPES,
            target_guard=GUARD,
            uow=FakeUnitOfWork(),
        ).execute(
            actor=READER,
            cmd=CreateWebhookSubscriptionCommand(
                name="X", url="https://x.example.com", event_types=["ProjectCreated"]
            ),
        )


async def test_create_rejects_unknown_event_type():
    with pytest.raises(InvalidWebhookConfigurationError):
        await CreateWebhookSubscription(
            FakeSubscriptionRepository(),
            FakeAdminSettingsRepository(),
            known_event_types=KNOWN_EVENT_TYPES,
            target_guard=GUARD,
            uow=FakeUnitOfWork(),
        ).execute(
            actor=ADMIN,
            cmd=CreateWebhookSubscriptionCommand(
                name="X", url="https://x.example.com", event_types=["Nope"]
            ),
        )


async def test_create_accepts_wildcard():
    result = await CreateWebhookSubscription(
        FakeSubscriptionRepository(),
        FakeAdminSettingsRepository(),
        known_event_types=KNOWN_EVENT_TYPES,
        target_guard=GUARD,
        uow=FakeUnitOfWork(),
    ).execute(
        actor=ADMIN,
        cmd=CreateWebhookSubscriptionCommand(
            name="X", url="https://x.example.com", event_types=["*"]
        ),
    )
    assert result.event_types == ["*"]


async def test_create_rejects_non_http_url():
    with pytest.raises(InvalidWebhookConfigurationError):
        await CreateWebhookSubscription(
            FakeSubscriptionRepository(),
            FakeAdminSettingsRepository(),
            known_event_types=KNOWN_EVENT_TYPES,
            target_guard=GUARD,
            uow=FakeUnitOfWork(),
        ).execute(
            actor=ADMIN,
            cmd=CreateWebhookSubscriptionCommand(
                name="X", url="ftp://x.example.com", event_types=["*"]
            ),
        )


# ── SSRF denylist ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/hook",
        "http://localhost/hook",
        "http://LOCALHOST/hook",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "http://10.0.0.5/hook",
        "http://172.16.0.5/hook",
        "http://192.168.1.5/hook",
        "http://[::1]/hook",  # IPv6 loopback
        "http://0.0.0.0/hook",
    ],
)
async def test_create_rejects_private_targets_by_default(url):
    with pytest.raises(InvalidWebhookConfigurationError):
        await CreateWebhookSubscription(
            FakeSubscriptionRepository(),
            FakeAdminSettingsRepository(allow_private_webhooks=False),
            known_event_types=KNOWN_EVENT_TYPES,
            target_guard=GUARD,
            uow=FakeUnitOfWork(),
        ).execute(
            actor=ADMIN,
            cmd=CreateWebhookSubscriptionCommand(name="X", url=url, event_types=["*"]),
        )


async def test_metadata_address_is_rejected_when_private_targets_are_off():
    """The finding's headline case (the cloud metadata endpoint) gets its
    own named test regardless of the parametrised case above covering the
    same IP, matching the shipped default explicitly rather than relying
    on FakeAdminSettingsRepository's default value."""
    with pytest.raises(InvalidWebhookConfigurationError):
        await CreateWebhookSubscription(
            FakeSubscriptionRepository(),
            FakeAdminSettingsRepository(allow_private_webhooks=False),
            known_event_types=KNOWN_EVENT_TYPES,
            target_guard=GUARD,
            uow=FakeUnitOfWork(),
        ).execute(
            actor=ADMIN,
            cmd=CreateWebhookSubscriptionCommand(
                name="X", url="http://169.254.169.254/latest/meta-data/", event_types=["*"]
            ),
        )


async def test_create_allows_private_targets_when_the_setting_is_on():
    """Default policy: an internal tool where pointing a webhook at
    another host on the same network is legitimate, not an attack."""
    result = await CreateWebhookSubscription(
        FakeSubscriptionRepository(),
        FakeAdminSettingsRepository(allow_private_webhooks=True),
        known_event_types=KNOWN_EVENT_TYPES,
        target_guard=GUARD,
        uow=FakeUnitOfWork(),
    ).execute(
        actor=ADMIN,
        cmd=CreateWebhookSubscriptionCommand(
            name="X", url="http://10.0.0.5/hook", event_types=["*"]
        ),
    )
    assert result.id > 0


async def test_create_allows_a_public_hostname_even_when_private_targets_are_disallowed():
    """The hostname is resolved, and it passes because it resolves to a
    public address. The same check runs again before every delivery."""
    result = await CreateWebhookSubscription(
        FakeSubscriptionRepository(),
        FakeAdminSettingsRepository(allow_private_webhooks=False),
        known_event_types=KNOWN_EVENT_TYPES,
        target_guard=GUARD,
        uow=FakeUnitOfWork(),
    ).execute(
        actor=ADMIN,
        cmd=CreateWebhookSubscriptionCommand(
            name="X", url="https://receiver.example.com/hook", event_types=["*"]
        ),
    )
    assert result.id > 0


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/hook",
        "http://169.254.169.254/latest/meta-data/",
        "http://redis:6379/",
        "http://localhost:3000/",
    ],
)
async def test_create_refuses_the_always_refused_set_even_when_private_targets_are_on(url):
    with pytest.raises(InvalidWebhookConfigurationError, match="never sends webhooks to"):
        await CreateWebhookSubscription(
            FakeSubscriptionRepository(),
            FakeAdminSettingsRepository(allow_private_webhooks=True),
            known_event_types=KNOWN_EVENT_TYPES,
            target_guard=GUARD,
            uow=FakeUnitOfWork(),
        ).execute(
            actor=ADMIN,
            cmd=CreateWebhookSubscriptionCommand(name="X", url=url, event_types=["*"]),
        )


async def test_create_refuses_a_host_that_does_not_resolve():
    with pytest.raises(InvalidWebhookConfigurationError, match="could not be resolved"):
        await CreateWebhookSubscription(
            FakeSubscriptionRepository(),
            FakeAdminSettingsRepository(allow_private_webhooks=True),
            known_event_types=KNOWN_EVENT_TYPES,
            target_guard=GUARD,
            uow=FakeUnitOfWork(),
        ).execute(
            actor=ADMIN,
            cmd=CreateWebhookSubscriptionCommand(
                name="X", url="https://nowhere.invalid/hook", event_types=["*"]
            ),
        )


async def test_update_also_rejects_private_targets_by_default():
    repo = FakeSubscriptionRepository([make_subscription(id=1)])
    with pytest.raises(InvalidWebhookConfigurationError):
        await UpdateWebhookSubscription(
            repo,
            FakeAdminSettingsRepository(allow_private_webhooks=False),
            known_event_types=KNOWN_EVENT_TYPES,
            target_guard=GUARD,
            uow=FakeUnitOfWork(),
        ).execute(
            actor=ADMIN,
            subscription_id=1,
            cmd=UpdateWebhookSubscriptionCommand(
                name="X", url="http://169.254.169.254/", event_types=["*"], is_active=True
            ),
        )


async def test_update_changes_fields_but_not_secret():
    repo = FakeSubscriptionRepository([make_subscription(id=1, secret="original")])
    result = await UpdateWebhookSubscription(
        repo,
        FakeAdminSettingsRepository(),
        known_event_types=KNOWN_EVENT_TYPES,
        target_guard=GUARD,
        uow=FakeUnitOfWork(),
    ).execute(
        actor=ADMIN,
        subscription_id=1,
        cmd=UpdateWebhookSubscriptionCommand(
            name="Renamed", url="https://new.example.com", event_types=["*"], is_active=False
        ),
    )
    assert result.name == "Renamed"
    assert (await repo.get_by_id(1)).secret == "original"


async def test_update_not_found_raises():
    with pytest.raises(WebhookSubscriptionNotFoundError):
        await UpdateWebhookSubscription(
            FakeSubscriptionRepository(),
            FakeAdminSettingsRepository(),
            known_event_types=KNOWN_EVENT_TYPES,
            target_guard=GUARD,
            uow=FakeUnitOfWork(),
        ).execute(
            actor=ADMIN,
            subscription_id=99,
            cmd=UpdateWebhookSubscriptionCommand(
                name="X", url="https://x.example.com", event_types=["*"], is_active=True
            ),
        )


async def test_delete_removes_subscription():
    repo = FakeSubscriptionRepository([make_subscription(id=1)])
    await DeleteWebhookSubscription(repo, uow=FakeUnitOfWork()).execute(
        actor=ADMIN, subscription_id=1
    )
    assert await repo.get_by_id(1) is None


# ── Dispatch ──────────────────────────────────────────────────────────


EVENT = ProjectCreated(project_id=1, project_number="P-1", actor_id=7, designated_user_id=4)


async def test_dispatch_passes_the_configured_webhook_timeout_to_the_dispatcher():
    """notifications.webhook_timeout_seconds is read fresh from the
    settings repo on every dispatch and forwarded as a per-call argument
    to IWebhookDispatcher.post, not baked into a long-lived dispatcher
    instance."""
    subs = FakeSubscriptionRepository([make_subscription(id=1)])
    deliveries = FakeDeliveryRepository()
    dispatcher = FakeDispatcher()
    settings = FakeAdminSettingsRepository(webhook_timeout_seconds=42)

    await DispatchEventToWebhooks(
        subs, deliveries, dispatcher, settings_repo=settings, uow=FakeUnitOfWork()
    ).execute(EVENT, "1-0")

    (call,) = dispatcher.calls
    assert call["timeout_seconds"] == 42


@pytest.mark.parametrize("allow_private", [True, False])
async def test_dispatch_passes_the_private_target_setting_to_the_dispatcher(allow_private):
    """The dispatcher checks the target again before sending, with the
    setting as it is at delivery time."""
    dispatcher = FakeDispatcher()
    await DispatchEventToWebhooks(
        FakeSubscriptionRepository([make_subscription(id=1)]),
        FakeDeliveryRepository(),
        dispatcher,
        settings_repo=FakeAdminSettingsRepository(allow_private_webhooks=allow_private),
        uow=FakeUnitOfWork(),
    ).execute(EVENT, "1-0")

    (call,) = dispatcher.calls
    assert call["allow_private"] is allow_private


async def test_retry_passes_the_private_target_setting_to_the_dispatcher():
    deliveries = FakeDeliveryRepository()
    await deliveries.save(
        WebhookDelivery(
            id=0,
            subscription_id=1,
            event_type="ProjectCreated",
            source_event_id="1-0",
            payload="{}",
            attempted_at=datetime.now(UTC),
            http_status=None,
            duration_ms=5,
            error="Timed out.",
            success=False,
        )
    )
    dispatcher = FakeDispatcher()
    await RetryWebhookDelivery(
        FakeSubscriptionRepository([make_subscription(id=1)]),
        deliveries,
        dispatcher,
        FakeAdminSettingsRepository(allow_private_webhooks=True),
        uow=FakeUnitOfWork(),
    ).execute(ADMIN, deliveries.saved[0].id)

    (call,) = dispatcher.calls
    assert call["allow_private"] is True


async def test_dispatch_delivers_to_matching_subscriptions_and_logs():
    subs = FakeSubscriptionRepository(
        [
            make_subscription(id=1, event_types=["ProjectCreated"]),
            make_subscription(id=2, url="https://all.example.com", event_types=["*"]),
            make_subscription(
                id=3, url="https://other.example.com", event_types=["OrderSubmitted"]
            ),
            make_subscription(id=4, url="https://off.example.com", is_active=False),
        ]
    )
    deliveries = FakeDeliveryRepository()
    dispatcher = FakeDispatcher()

    await DispatchEventToWebhooks(
        subs,
        deliveries,
        dispatcher,
        settings_repo=FakeAdminSettingsRepository(),
        uow=FakeUnitOfWork(),
    ).execute(EVENT, "1-0")

    assert {c["url"] for c in dispatcher.calls} == {
        "https://receiver.example.com/hook",
        "https://all.example.com",
    }
    assert len(deliveries.saved) == 2
    assert all(d.success and d.http_status == 200 for d in deliveries.saved)

    # Matched by URL, not by position: fan-out is concurrent, so call order
    # is nondeterministic. The assertion's intent was always "the body is
    # right", never "subscriber 1 goes first".
    (call,) = [c for c in dispatcher.calls if c["url"] == "https://all.example.com"]
    body = json.loads(call["payload"])
    assert body == {
        "id": "1-0",
        "event": "ProjectCreated",
        "data": {"project_id": 1, "project_number": "P-1", "actor_id": 7, "designated_user_id": 4},
    }


async def test_dispatch_without_matching_subscription_is_a_noop():
    dispatcher = FakeDispatcher()
    await DispatchEventToWebhooks(
        FakeSubscriptionRepository([make_subscription(event_types=["OrderSubmitted"])]),
        FakeDeliveryRepository(),
        dispatcher,
        settings_repo=FakeAdminSettingsRepository(),
        uow=FakeUnitOfWork(),
    ).execute(EVENT, "1-0")
    assert dispatcher.calls == []


async def test_dispatch_failure_logs_and_raises_for_retry():
    subs = FakeSubscriptionRepository([make_subscription(id=1)])
    deliveries = FakeDeliveryRepository()
    dispatcher = FakeDispatcher(
        {
            "https://receiver.example.com/hook": WebhookDispatchResult(
                http_status=500, duration_ms=12, error=None
            )
        }
    )

    with pytest.raises(WebhookDeliveryFailedError):
        await DispatchEventToWebhooks(
            subs,
            deliveries,
            dispatcher,
            settings_repo=FakeAdminSettingsRepository(),
            uow=FakeUnitOfWork(),
        ).execute(EVENT, "1-0")

    (logged,) = deliveries.saved
    assert logged.success is False
    assert logged.http_status == 500


async def test_redelivery_skips_already_successful_subscribers():
    ok = make_subscription(id=1, url="https://ok.example.com")
    failing = make_subscription(id=2, url="https://down.example.com")
    subs = FakeSubscriptionRepository([ok, failing])
    deliveries = FakeDeliveryRepository()

    dispatcher = FakeDispatcher(
        {"https://down.example.com": WebhookDispatchResult(None, 10_000, "timeout")}
    )
    use_case = DispatchEventToWebhooks(
        subs,
        deliveries,
        dispatcher,
        settings_repo=FakeAdminSettingsRepository(),
        uow=FakeUnitOfWork(),
    )

    with pytest.raises(WebhookDeliveryFailedError):
        await use_case.execute(EVENT, "1-0")

    # Redelivery of the same message: only the failed subscriber is retried.
    dispatcher_retry = FakeDispatcher()
    await DispatchEventToWebhooks(
        subs,
        deliveries,
        dispatcher_retry,
        settings_repo=FakeAdminSettingsRepository(),
        uow=FakeUnitOfWork(),
    ).execute(EVENT, "1-0")

    assert [c["url"] for c in dispatcher_retry.calls] == ["https://down.example.com"]


# ── Circuit breaker ─────────────────────────────────────────────────


async def _seed_attempts(deliveries, subscription_id, outcomes, newest_age):
    """Saves one past attempt per outcome, oldest first, the newest one
    `newest_age` ago and the others a second apart before it."""
    newest = datetime.now(UTC) - newest_age
    for index, success in enumerate(outcomes):
        await deliveries.save(
            WebhookDelivery(
                id=0,
                subscription_id=subscription_id,
                event_type="ProjectCreated",
                source_event_id=f"0-{index}",
                payload="{}",
                attempted_at=newest - timedelta(seconds=len(outcomes) - 1 - index),
                http_status=200 if success else None,
                duration_ms=5,
                error=None if success else "timeout",
                success=success,
            )
        )


async def test_open_circuit_skips_the_post_and_still_raises_for_retry():
    down = make_subscription(id=1, name="Down", url="https://down.example.com")
    healthy = make_subscription(id=2, name="Healthy", url="https://ok.example.com")
    deliveries = FakeDeliveryRepository()
    await _seed_attempts(deliveries, 1, [False] * 5, timedelta(seconds=5))
    dispatcher = FakeDispatcher()

    with pytest.raises(WebhookDeliveryFailedError, match="Down"):
        await DispatchEventToWebhooks(
            FakeSubscriptionRepository([down, healthy]),
            deliveries,
            dispatcher,
            settings_repo=FakeAdminSettingsRepository(),
            uow=FakeUnitOfWork(),
        ).execute(EVENT, "9-0")

    assert [c["url"] for c in dispatcher.calls] == ["https://ok.example.com"]
    # The skip writes no delivery row, so the cooldown keeps running from the
    # last real attempt.
    assert [d.subscription_id for d in deliveries.saved[5:]] == [2]


async def test_circuit_half_opens_after_the_cooldown_and_probes():
    deliveries = FakeDeliveryRepository()
    await _seed_attempts(deliveries, 1, [False] * 5, timedelta(seconds=61))
    dispatcher = FakeDispatcher()

    await DispatchEventToWebhooks(
        FakeSubscriptionRepository([make_subscription(id=1)]),
        deliveries,
        dispatcher,
        settings_repo=FakeAdminSettingsRepository(),
        uow=FakeUnitOfWork(),
    ).execute(EVENT, "9-0")

    assert len(dispatcher.calls) == 1
    assert deliveries.saved[-1].success is True


@pytest.mark.parametrize(
    "outcomes",
    [[False] * 4, [True, False, False, False, False], [False, False, False, False, True]],
    ids=["too-few-failures", "older-success-within-window", "latest-success"],
)
async def test_circuit_stays_closed_without_five_consecutive_failures(outcomes):
    deliveries = FakeDeliveryRepository()
    await _seed_attempts(deliveries, 1, outcomes, timedelta(seconds=5))
    dispatcher = FakeDispatcher()

    await DispatchEventToWebhooks(
        FakeSubscriptionRepository([make_subscription(id=1)]),
        deliveries,
        dispatcher,
        settings_repo=FakeAdminSettingsRepository(),
        uow=FakeUnitOfWork(),
    ).execute(EVENT, "9-0")

    assert len(dispatcher.calls) == 1


async def test_failed_probe_reopens_the_circuit_for_the_next_message():
    deliveries = FakeDeliveryRepository()
    await _seed_attempts(deliveries, 1, [False] * 5, timedelta(seconds=61))
    subs = FakeSubscriptionRepository([make_subscription(id=1)])
    dispatcher = FakeDispatcher(
        {"https://receiver.example.com/hook": WebhookDispatchResult(None, 10_000, "timeout")}
    )
    use_case = DispatchEventToWebhooks(
        subs,
        deliveries,
        dispatcher,
        settings_repo=FakeAdminSettingsRepository(),
        uow=FakeUnitOfWork(),
    )

    for message_id in ("9-0", "9-1"):
        with pytest.raises(WebhookDeliveryFailedError):
            await use_case.execute(EVENT, message_id)

    assert [c["delivery_id"] for c in dispatcher.calls] == ["9-0"]


async def test_the_read_transaction_ends_before_any_post():
    """The read transaction commits before any receiver is contacted, and
    the delivery rows are recorded and committed in a second transaction
    once every post has answered."""
    events = []

    class RecordingUow:
        async def commit(self):
            events.append("commit")

        async def rollback(self):
            events.append("rollback")

    class RecordingDispatcher(FakeDispatcher):
        async def post(self, **kwargs):
            events.append("post")
            return await super().post(**kwargs)

    class RecordingDeliveries(FakeDeliveryRepository):
        async def save(self, delivery):
            events.append("save")
            return await super().save(delivery)

    await DispatchEventToWebhooks(
        FakeSubscriptionRepository([make_subscription(id=1)]),
        RecordingDeliveries(),
        RecordingDispatcher(),
        settings_repo=FakeAdminSettingsRepository(),
        uow=RecordingUow(),
    ).execute(EVENT, "1-0")

    assert events == ["commit", "post", "save", "commit"]


async def test_failed_deliveries_are_committed_before_the_failure_is_raised():
    """The redelivered message must find the recorded attempts, so the rows
    commit before WebhookDeliveryFailedError propagates."""
    uow = FakeUnitOfWork()
    dispatcher = FakeDispatcher(
        {"https://receiver.example.com/hook": WebhookDispatchResult(None, 10_000, "timeout")}
    )

    with pytest.raises(WebhookDeliveryFailedError):
        await DispatchEventToWebhooks(
            FakeSubscriptionRepository([make_subscription(id=1)]),
            FakeDeliveryRepository(),
            dispatcher,
            settings_repo=FakeAdminSettingsRepository(),
            uow=uow,
        ).execute(EVENT, "1-0")

    assert uow.commits == 2


async def test_a_retry_ends_the_read_transaction_before_posting():
    """A retry commits its reads before contacting the receiver and records
    the new attempt in its own transaction afterwards."""
    events = []

    class RecordingUow:
        async def commit(self):
            events.append("commit")

        async def rollback(self):
            events.append("rollback")

    class RecordingDispatcher(FakeDispatcher):
        async def post(self, **kwargs):
            events.append("post")
            return await super().post(**kwargs)

    deliveries = FakeDeliveryRepository()
    await _seed_attempts(deliveries, 1, [False], timedelta(seconds=5))

    class RecordingDeliveries(FakeDeliveryRepository):
        async def save(self, delivery):
            events.append("save")
            return await deliveries.save(delivery)

        async def get_by_id(self, delivery_id):
            return await deliveries.get_by_id(delivery_id)

    await RetryWebhookDelivery(
        FakeSubscriptionRepository([make_subscription(id=1)]),
        RecordingDeliveries(),
        RecordingDispatcher(),
        FakeAdminSettingsRepository(),
        uow=RecordingUow(),
    ).execute(make_user(permissions=[Permission.WRITE_SETTINGS]), deliveries.saved[0].id)

    assert events == ["commit", "post", "save", "commit"]


# ── Concurrent fan-out ──────────────────────────────────────────────


def _four_matching_subscriptions() -> FakeSubscriptionRepository:
    return FakeSubscriptionRepository(
        [make_subscription(id=i, url=f"https://sub{i}.example.com") for i in range(1, 5)]
    )


async def test_dispatch_posts_to_subscribers_concurrently():
    dispatcher = FakeDispatcher(delay_seconds=0.2)
    deliveries = FakeDeliveryRepository()

    started = time.monotonic()
    await DispatchEventToWebhooks(
        _four_matching_subscriptions(),
        deliveries,
        dispatcher,
        settings_repo=FakeAdminSettingsRepository(),
        uow=FakeUnitOfWork(),
    ).execute(EVENT, "1-0")
    elapsed = time.monotonic() - started

    assert len(dispatcher.calls) == 4
    assert elapsed < 0.5  # >= 0.8 s if the four 0.2 s posts were serialised


async def test_a_slow_subscriber_does_not_prevent_others_from_being_recorded():
    dispatcher = FakeDispatcher(
        {"https://sub1.example.com": WebhookDispatchResult(None, 10_000, "timeout")},
        delay_seconds=0.2,
    )
    deliveries = FakeDeliveryRepository()

    with pytest.raises(WebhookDeliveryFailedError):
        await DispatchEventToWebhooks(
            _four_matching_subscriptions(),
            deliveries,
            dispatcher,
            settings_repo=FakeAdminSettingsRepository(),
            uow=FakeUnitOfWork(),
        ).execute(EVENT, "1-0")

    assert len(deliveries.saved) == 4  # every attempt recorded, slow one included
    assert [d.success for d in deliveries.saved] == [False, True, True, True]


async def test_delivery_rows_are_never_written_while_posts_are_in_flight():
    """Pins the session-affinity constraint: the handler shares one
    AsyncSession, which must never run two operations at once, so only the
    HTTP posts may overlap. Every repository call has to happen while no
    post is in flight and while no other repository call is running, and
    the delivery rows are written in subscription order."""

    class OverlapRecordingDeliveryRepository(FakeDeliveryRepository):
        def __init__(self, dispatcher: FakeDispatcher):
            super().__init__()
            self._dispatcher = dispatcher
            self._in_flight = 0
            self.max_in_flight = 0
            self.posts_in_flight_seen: set[int] = set()

        async def _enter(self) -> None:
            self.posts_in_flight_seen.add(self._dispatcher.in_flight)
            self._in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self._in_flight)
            await asyncio.sleep(0)

        async def save(self, delivery):
            await self._enter()
            try:
                return await super().save(delivery)
            finally:
                self._in_flight -= 1

        async def exists_success(self, subscription_id, source_event_id):
            await self._enter()
            try:
                return await super().exists_success(subscription_id, source_event_id)
            finally:
                self._in_flight -= 1

    dispatcher = FakeDispatcher(delay_seconds=0.05)
    deliveries = OverlapRecordingDeliveryRepository(dispatcher)

    await DispatchEventToWebhooks(
        _four_matching_subscriptions(),
        deliveries,
        dispatcher,
        settings_repo=FakeAdminSettingsRepository(),
        uow=FakeUnitOfWork(),
    ).execute(EVENT, "1-0")

    assert dispatcher.max_in_flight > 1  # HTTP really went concurrent
    assert deliveries.posts_in_flight_seen == {0}  # DB never overlapped HTTP
    assert deliveries.max_in_flight == 1  # nor another DB call
    assert [d.subscription_id for d in deliveries.saved] == [1, 2, 3, 4]


async def test_concurrent_dispatch_still_raises_when_any_subscriber_fails():
    failure = WebhookDispatchResult(http_status=500, duration_ms=9, error=None)
    dispatcher = FakeDispatcher({"https://sub3.example.com": failure})

    with pytest.raises(WebhookDeliveryFailedError) as excinfo:
        await DispatchEventToWebhooks(
            _four_matching_subscriptions(),
            FakeDeliveryRepository(),
            dispatcher,
            settings_repo=FakeAdminSettingsRepository(),
            uow=FakeUnitOfWork(),
        ).execute(EVENT, "1-0")

    assert "Hook 3" in str(excinfo.value)


# ── Deliveries log + manual retry ─────────────────────────────────────


async def test_get_deliveries_requires_read_settings():
    with pytest.raises(InsufficientPermissionsError):
        await GetWebhookDeliveries(
            FakeSubscriptionRepository([make_subscription(id=1)]), FakeDeliveryRepository()
        ).execute(actor=make_user(id=9, permissions=[]), subscription_id=1)


async def test_get_failed_deliveries_returns_only_failures_newest_first():
    subs = FakeSubscriptionRepository(
        [
            make_subscription(id=1, url="https://ok.example.com"),
            make_subscription(id=2, url="https://down.example.com"),
        ]
    )
    deliveries = FakeDeliveryRepository()
    dispatcher = FakeDispatcher(
        {"https://down.example.com": WebhookDispatchResult(None, 10_000, "timeout")}
    )
    with pytest.raises(WebhookDeliveryFailedError):
        await DispatchEventToWebhooks(
            subs,
            deliveries,
            dispatcher,
            settings_repo=FakeAdminSettingsRepository(),
            uow=FakeUnitOfWork(),
        ).execute(EVENT, "1-0")

    result = await GetFailedWebhookDeliveries(deliveries).execute(actor=READER)

    assert result.total == 1
    assert [d.subscription_id for d in result.items] == [2]
    assert all(d.success is False for d in result.items)


async def test_get_failed_deliveries_requires_read_settings():
    with pytest.raises(InsufficientPermissionsError):
        await GetFailedWebhookDeliveries(FakeDeliveryRepository()).execute(
            actor=make_user(id=9, permissions=[])
        )


async def test_a_failed_delivery_found_via_the_failed_list_can_be_retried():
    """Pins that discovery feeds the existing replay path: the cross-
    subscription failed list is only useful if its ids are the ids
    RetryWebhookDelivery takes."""
    subs = FakeSubscriptionRepository([make_subscription(id=1)])
    deliveries = FakeDeliveryRepository()
    failing = FakeDispatcher(
        {"https://receiver.example.com/hook": WebhookDispatchResult(None, 10_000, "timeout")}
    )
    with pytest.raises(WebhookDeliveryFailedError):
        await DispatchEventToWebhooks(
            subs,
            deliveries,
            failing,
            settings_repo=FakeAdminSettingsRepository(),
            uow=FakeUnitOfWork(),
        ).execute(EVENT, "1-0")

    listed = await GetFailedWebhookDeliveries(deliveries).execute(actor=ADMIN)
    (failed,) = listed.items

    result = await RetryWebhookDelivery(
        subs, deliveries, FakeDispatcher(), FakeAdminSettingsRepository(), uow=FakeUnitOfWork()
    ).execute(actor=ADMIN, delivery_id=failed.id)

    assert result.success is True
    assert len(deliveries.saved) == 2  # appended, original untouched
    assert (await GetFailedWebhookDeliveries(deliveries).execute(actor=ADMIN)).total == 1


async def test_manual_retry_appends_new_log_entry():
    subs = FakeSubscriptionRepository([make_subscription(id=1)])
    deliveries = FakeDeliveryRepository()
    failing = FakeDispatcher(
        {"https://receiver.example.com/hook": WebhookDispatchResult(None, 10_000, "timeout")}
    )
    with pytest.raises(WebhookDeliveryFailedError):
        await DispatchEventToWebhooks(
            subs,
            deliveries,
            failing,
            settings_repo=FakeAdminSettingsRepository(),
            uow=FakeUnitOfWork(),
        ).execute(EVENT, "1-0")
    original = deliveries.saved[0]

    result = await RetryWebhookDelivery(
        subs, deliveries, FakeDispatcher(), FakeAdminSettingsRepository(), uow=FakeUnitOfWork()
    ).execute(actor=ADMIN, delivery_id=original.id)

    assert result.success is True
    assert result.id != original.id  # appended, not mutated
    assert result.payload == original.payload
    assert len(deliveries.saved) == 2
