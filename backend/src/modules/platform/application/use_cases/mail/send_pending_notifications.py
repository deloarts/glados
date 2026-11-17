"""
Drains the email_notification queue.

Called periodically by the background scheduler (main.py). For each
distinct receiver, it checks that mail and email notifications are
enabled in admin settings, looks up the receiver's email address, sends
a digest email via the mail service, and deletes the successfully sent
records from the queue, committing each receiver's deletes on their own.

Each receiver is processed independently so a single bad address does not
block everyone else.
"""

from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.mail_service_port import IMailService
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.email_notification_repository import (
    IEmailNotificationRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class SendPendingNotifications:
    def __init__(
        self,
        notification_repo: IEmailNotificationRepository,
        user_repo: IUserRepository,
        mail_service: IMailService,
        admin_settings_repo: IPlatformSettingsRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._uow = uow
        self._notifications = notification_repo
        self._users = user_repo
        self._mail = mail_service
        self._settings = admin_settings_repo

    async def execute(self) -> int:
        """Send all queued notifications. Returns the number of emails sent."""
        features = await self._settings.get_features()
        if not features.enable_email_notifications:
            return 0

        mail_settings = await self._settings.get_mail()
        if not mail_settings.enabled:
            return 0

        receiver_ids = await self._notifications.get_distinct_receiver_ids()
        if not receiver_ids:
            return 0

        sent = 0
        for receiver_id in receiver_ids:
            items = await self._notifications.get_by_receiver_id(receiver_id)
            if not items:
                continue

            user = await self._users.get_by_id(receiver_id)
            if not user:
                log.warning(
                    "Notification queue has records for unknown user id=%s; skipping.",
                    receiver_id,
                )
                continue

            if not user.is_active:
                log.debug(
                    "Skipping notifications for inactive user %r (id=%s).",
                    user.username,
                    receiver_id,
                )
                continue

            try:
                await self._mail.send_notification_digest(
                    to=user.email,
                    full_name=user.full_name,
                    items=items,
                    language=user.language,
                )
                for item in items:
                    await self._notifications.delete_by_id(item.id)
                await self._uow.commit()
                sent += 1
                log.info(
                    "Sent notification digest to %r (id=%s): %d item(s).",
                    user.username,
                    receiver_id,
                    len(items),
                )
            except Exception:
                log.exception(
                    "Failed to send notification digest to %r (id=%s); will retry next run.",
                    user.username,
                    receiver_id,
                )

        return sent
