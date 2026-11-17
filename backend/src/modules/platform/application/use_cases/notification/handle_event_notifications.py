"""
Turns domain events into in-app notifications (and email digest entries).
Invoked by the event bus worker for every message in the "notifications"
consumer group. The notify-whom rules live with the modules whose events
they read: each module registers its rules at startup through
src/bootstrap/registrations.py, and the rules for user events live here.
A rule gets the handler as its `NotificationSender`, the toolkit every rule
shares for saving notifications, finding recipients and sending mail.

Idempotency: each in-app notification stores the producer's event id that
produced it (source_event_id), unique per user in the database. A
redelivered or republished event whose notifications exist is skipped
before any rule runs. Two deliveries of one event can also run at the same
time, when the reclaim scan hands a slow handler's message to another
worker; the notification insert of the later one then waits for the
earlier transaction and inserts nothing, and the later handler rolls back
everything it staged and stops, mails included. Every row one event
produces, email digest entries included, commits in one unit of work, so a
crash never leaves the idempotency marker without its digest entry or half
of a broadcast. Rules that also send a system mail commit before sending
it, so a mail never goes out for a notification that was rolled back.

Events are routed through the rule table keyed by event type; events
without a rule produce no notifications.

Some events (account_deactivated, permissions_changed, project_assigned,
product_assigned) also fire an immediate system mail alongside the in-app
row. `user_repo`, `mail_service` and `admin_settings_repo` are optional;
when any of them is absent, mail sending is skipped and only the in-app and
email-digest behaviour runs. Mail sends are non-fatal: a failure is logged
and never breaks event handling.
"""

from collections.abc import Mapping
from typing import Any

from src.modules.platform.application.services.notification_rules import NotificationRule
from src.modules.platform.application.services.notification_rules import NotificationSender
from src.modules.platform.application.services.paging import fetch_all
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.entities.email_notification import EmailNotification
from src.modules.platform.domain.entities.notification import Notification
from src.modules.platform.domain.entities.notification import make_notification
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.events.user_events import UserDeactivated
from src.modules.platform.domain.events.user_events import UserForcedLogout
from src.modules.platform.domain.events.user_events import UserPermissionsChanged
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind
from src.modules.platform.domain.value_objects.notification_type import NotificationType
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.mail_service_port import IMailService
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.email_notification_repository import (
    IEmailNotificationRepository,
)
from src.modules.platform.ports.outbound.repositories.notification_repository import (
    INotificationRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_repository import UserFilterDto
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.events.base import DomainEvent


async def _on_permissions_changed(
    sender: NotificationSender, event: UserPermissionsChanged, source_event_id: str
) -> None:
    if event.actor_id == event.user_id:
        return
    await sender.notify(
        make_notification(
            user_id=event.user_id,
            type=NotificationType.PERMISSIONS_CHANGED,
            title="Permissions updated",
            message="Your account permissions have been updated by an administrator.",
            source_event_id=source_event_id,
        )
    )
    await sender.commit()
    await sender.mail_active_user(MailTemplateKind.PERMISSIONS_CHANGED, event.user_id)


async def _on_user_deactivated(
    sender: NotificationSender, event: UserDeactivated, source_event_id: str
) -> None:
    if event.actor_id == event.user_id:
        return
    await sender.notify(
        make_notification(
            user_id=event.user_id,
            type=NotificationType.ACCOUNT_DEACTIVATED,
            title="Account deactivated",
            message="Your account has been deactivated.",
            source_event_id=source_event_id,
        )
    )
    await sender.commit()
    # Deliberately no is_active check here (unlike mail_active_user, used by
    # every other event mail): this is the deactivation itself, so the target user's row
    # already reads is_active=False when this handler runs, and the in-app notification
    # is useless to someone who can no longer log in to see it.
    await sender.mail_user(MailTemplateKind.ACCOUNT_DEACTIVATED, event.user_id)


async def _on_forced_logout(
    sender: NotificationSender, event: UserForcedLogout, source_event_id: str
) -> None:
    await sender.notify(
        make_notification(
            user_id=event.user_id,
            type=NotificationType.FORCED_LOGOUT,
            title="Logged out by administrator",
            message="You have been logged out by an administrator.",
            source_event_id=source_event_id,
        )
    )


_RULES: dict[type[DomainEvent], NotificationRule] = {
    UserPermissionsChanged: _on_permissions_changed,
    UserDeactivated: _on_user_deactivated,
    UserForcedLogout: _on_forced_logout,
}


def register_notification_rules(rules: Mapping[type[DomainEvent], NotificationRule]) -> None:
    """Adds the rules a module sends notifications by. One event type has
    one rule; registering another for a taken type is an error."""
    for event_type, rule in rules.items():
        known = _RULES.setdefault(event_type, rule)
        if known is not rule:
            raise ValueError(f"{event_type.__name__} already has a notification rule.")


class _HandledElsewhere(Exception):
    """A concurrent delivery of the same event wrote its notifications."""


class HandleEventNotifications:
    def __init__(
        self,
        inapp_notification_repo: INotificationRepository,
        email_notification_repo: IEmailNotificationRepository,
        user_repo: IUserRepository | None = None,
        mail_service: IMailService | None = None,
        admin_settings_repo: IPlatformSettingsRepository | None = None,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._uow = uow
        self._inapp = inapp_notification_repo
        self._emails = email_notification_repo
        self._users = user_repo
        self._mail_service = mail_service
        self._admin_settings = admin_settings_repo

    async def execute(self, event: DomainEvent, source_event_id: str) -> None:
        if await self._inapp.exists_by_source_event_id(source_event_id):
            return  # redelivered message, already handled

        rule = self._rule_for(event)
        if rule is None:
            return
        try:
            await rule(self, event, source_event_id)
        except _HandledElsewhere:
            await self._uow.rollback()
            log.info(
                "Notifications for event %s were written by a concurrent delivery; skipped.",
                source_event_id,
            )
            return
        await self._uow.commit()

    def _rule_for(self, event: DomainEvent) -> NotificationRule | None:
        """Looks the rule up along the event's MRO so a subclass of a mapped event is
        handled like its parent, the same result an isinstance check gives. Events without a
        rule produce no notifications."""
        for cls in type(event).__mro__:
            rule = _RULES.get(cls)
            if rule is not None:
                return rule
        return None

    # ── The toolkit rules share ──────────────────────────────────────

    async def notify(self, notification: Notification) -> None:
        """Adds the notification, or stops the rule when another delivery
        of the same event already added it for this user."""
        if not await self._inapp.add_for_event(notification):
            raise _HandledElsewhere

    async def queue_digest(self, entry: EmailNotification) -> None:
        await self._emails.save(entry)

    async def commit(self) -> None:
        await self._uow.commit()

    async def users_with_permission(self, permission: str) -> list[User]:
        """Every active user holding `permission`, paginated internally
        since IUserRepository.get_multi caps an unspecified limit at
        DEFAULT_PAGE_SIZE: a broadcast notification (unlike every other
        event here, which targets one already-known user_id) needs the
        whole set, not one page of it."""
        if self._users is None:
            return []
        users = self._users
        active = await fetch_all(
            lambda skip, limit: users.get_multi(
                UserFilterDto(is_active=True, skip=skip, limit=limit)
            ),
            MAX_PAGE_SIZE,
        )
        return [u for u in active if u.has_permission(permission)]

    # ── Event mail ───────────────────────────────────────────────────

    async def mail_enabled(self) -> bool:
        """features.enable_email_notifications AND mail.enabled: the same
        two checks SendPendingNotifications makes before draining the
        digest queue. No per-user opt-out, matching that precedent."""
        if self._mail_service is None or self._admin_settings is None or self._users is None:
            return False
        if not (await self._admin_settings.get_features()).enable_email_notifications:
            return False
        return (await self._admin_settings.get_mail()).enabled

    async def mail_active_user(
        self, kind: MailTemplateKind, user_id: int, **extra_ctx: Any
    ) -> None:
        """Skips a user who is no longer active, unlike
        `mail_user` (account_deactivated only): every other event
        mail is about something an inactive account has no use for."""
        if not await self.mail_enabled():
            return
        assert self._users is not None  # guaranteed by mail_enabled above
        user = await self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            return
        await self.send_mail(kind, user, **extra_ctx)

    async def mail_user(self, kind: MailTemplateKind, user_id: int, **extra_ctx: Any) -> None:
        """Sends unconditionally on the target user's active/inactive
        state (only account_deactivated uses this; see its call site)."""
        if not await self.mail_enabled():
            return
        assert self._users is not None  # guaranteed by mail_enabled above
        user = await self._users.get_by_id(user_id)
        if user is None:
            return
        await self.send_mail(kind, user, **extra_ctx)

    async def send_mail(self, kind: MailTemplateKind, user: User, **extra_ctx: Any) -> None:
        assert self._mail_service is not None  # guaranteed by mail_enabled
        try:
            await self._mail_service.send_system_mail(
                kind,
                to=user.email,
                language=user.language,
                full_name=user.full_name,
                **extra_ctx,
            )
        except Exception:
            # Never let a broken template or an SMTP hiccup break event
            # handling: the in-app row (already committed above) still
            # stands, same "non-fatal, log and move on" contract as
            # CreateUser's welcome-mail send.
            log.exception("Failed to send %s mail to user id=%s.", kind.value, user.id)
