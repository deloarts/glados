"""
Admin CRUD for webhook subscriptions. Reads require read:settings, writes
require write:settings. The signing secret is generated here and returned
only from the create use case, every other read path omits it.

Create and update hand the URL to the webhook target guard, which resolves
the host and refuses loopback, link-local and cloud metadata addresses,
reserved ranges, the stack's own network and its service names. Private
ranges pass while AdminFeatureSettings.allow_private_webhooks is on, the
default, since another host on the company network is a normal receiver
for an internal system. The dispatcher runs the same check again before
every delivery, so a hostname that later resolves elsewhere is still
caught.
"""

import base64
import secrets

from src.modules.platform.application.dto.webhook_dto import CreatedWebhookSubscriptionResult
from src.modules.platform.application.dto.webhook_dto import CreateWebhookSubscriptionCommand
from src.modules.platform.application.dto.webhook_dto import UpdateWebhookSubscriptionCommand
from src.modules.platform.application.dto.webhook_dto import WebhookSubscriptionResult
from src.modules.platform.application.mappers.webhook_mapper import WebhookMapper
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.entities.webhook_subscription import WebhookSubscription
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import InvalidWebhookConfigurationError
from src.modules.platform.domain.exceptions import WebhookSubscriptionNotFoundError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.webhook_subscription_repository import (
    IWebhookSubscriptionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.platform.ports.outbound.webhook_target_guard_port import IWebhookTargetGuard
from src.shared_kernel.domain.services.clock import now_utc


def _assert_can_read(actor: User) -> None:
    if not actor.has_permission(Permission.READ_SETTINGS):
        raise InsufficientPermissionsError("Reading webhook settings requires read:settings.")


def _assert_can_write(actor: User) -> None:
    if not actor.has_permission(Permission.WRITE_SETTINGS):
        raise InsufficientPermissionsError("Changing webhook settings requires write:settings.")


def new_signing_secret() -> str:
    """A Standard Webhooks secret: `whsec_` and 32 random bytes in base64."""
    return "whsec_" + base64.b64encode(secrets.token_bytes(32)).decode()


async def _assert_valid_config(
    url: str,
    event_types: list[str],
    known_event_types: set[str],
    guard: IWebhookTargetGuard,
    *,
    allow_private: bool,
) -> None:
    if not event_types:
        raise InvalidWebhookConfigurationError(
            'At least one event type is required (use ["*"] to subscribe to all events).'
        )
    unknown = set(event_types) - known_event_types - {"*"}
    if unknown:
        raise InvalidWebhookConfigurationError(f"Unknown event type(s): {sorted(unknown)}.")
    await guard.resolve(url, allow_private=allow_private)


class CreateWebhookSubscription:
    def __init__(
        self,
        subscription_repo: IWebhookSubscriptionRepository,
        settings_repo: IPlatformSettingsRepository,
        known_event_types: set[str],
        *,
        target_guard: IWebhookTargetGuard,
        uow: IUnitOfWork,
    ) -> None:
        self._subscriptions = subscription_repo
        self._settings = settings_repo
        self._known_event_types = known_event_types
        self._guard = target_guard
        self._uow = uow

    async def execute(
        self, actor: User, cmd: CreateWebhookSubscriptionCommand
    ) -> CreatedWebhookSubscriptionResult:
        _assert_can_write(actor)
        await _assert_valid_config(
            cmd.url,
            cmd.event_types,
            self._known_event_types,
            self._guard,
            allow_private=(await self._settings.get_features()).allow_private_webhooks,
        )

        subscription = WebhookSubscription(
            id=0,
            name=cmd.name,
            url=cmd.url,
            secret=new_signing_secret(),
            event_types=cmd.event_types,
            is_active=cmd.is_active,
            created=now_utc(),
            creator_id=actor.id,
        )
        saved = await self._subscriptions.save(subscription)
        await self._uow.commit()

        log.info(
            f"Created webhook subscription {saved.name!r} (ID={saved.id}) for {saved.event_types}."
        )
        return WebhookMapper.to_created_result(saved)


class GetWebhookSubscriptions:
    def __init__(self, subscription_repo: IWebhookSubscriptionRepository) -> None:
        self._subscriptions = subscription_repo

    async def execute(self, actor: User) -> list[WebhookSubscriptionResult]:
        _assert_can_read(actor)
        return [WebhookMapper.to_result(s) for s in await self._subscriptions.get_all()]


class UpdateWebhookSubscription:
    def __init__(
        self,
        subscription_repo: IWebhookSubscriptionRepository,
        settings_repo: IPlatformSettingsRepository,
        known_event_types: set[str],
        *,
        target_guard: IWebhookTargetGuard,
        uow: IUnitOfWork,
    ) -> None:
        self._subscriptions = subscription_repo
        self._settings = settings_repo
        self._known_event_types = known_event_types
        self._guard = target_guard
        self._uow = uow

    async def execute(
        self, actor: User, subscription_id: int, cmd: UpdateWebhookSubscriptionCommand
    ) -> WebhookSubscriptionResult:
        _assert_can_write(actor)

        subscription = await self._subscriptions.get_by_id(subscription_id)
        if not subscription:
            raise WebhookSubscriptionNotFoundError(
                f"Webhook subscription #{subscription_id} not found."
            )

        await _assert_valid_config(
            cmd.url,
            cmd.event_types,
            self._known_event_types,
            self._guard,
            allow_private=(await self._settings.get_features()).allow_private_webhooks,
        )

        subscription.name = cmd.name
        subscription.url = cmd.url
        subscription.event_types = cmd.event_types
        subscription.is_active = cmd.is_active
        saved = await self._subscriptions.save(subscription)
        await self._uow.commit()

        log.info(f"Updated webhook subscription {saved.name!r} (ID={saved.id}).")
        return WebhookMapper.to_result(saved)


class DeleteWebhookSubscription:
    def __init__(
        self,
        subscription_repo: IWebhookSubscriptionRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._subscriptions = subscription_repo
        self._uow = uow

    async def execute(self, actor: User, subscription_id: int) -> None:
        _assert_can_write(actor)

        subscription = await self._subscriptions.get_by_id(subscription_id)
        if not subscription:
            raise WebhookSubscriptionNotFoundError(
                f"Webhook subscription #{subscription_id} not found."
            )

        await self._subscriptions.delete(subscription_id)
        await self._uow.commit()
        log.info(f"Deleted webhook subscription {subscription.name!r} (ID={subscription_id}).")
