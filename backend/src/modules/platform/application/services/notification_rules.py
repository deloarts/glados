"""
The contract between Platform's notification handler and the rules each
module registers at startup: a rule takes the handler as its
NotificationSender, the toolkit for saving notifications, finding
recipients and sending mail, and the event it is registered for.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any
from typing import Protocol

from src.modules.platform.domain.entities.email_notification import EmailNotification
from src.modules.platform.domain.entities.notification import Notification
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind


class NotificationSender(Protocol):
    """What a notification rule may do: save in-app notifications and digest
    entries, find recipients, commit before a mail and send mail."""

    async def notify(self, notification: Notification) -> None: ...

    async def queue_digest(self, entry: EmailNotification) -> None: ...

    async def users_with_permission(self, permission: str) -> list[User]: ...

    async def commit(self) -> None: ...

    async def mail_enabled(self) -> bool: ...

    async def mail_active_user(
        self, kind: MailTemplateKind, user_id: int, **extra_ctx: Any
    ) -> None: ...

    async def mail_user(self, kind: MailTemplateKind, user_id: int, **extra_ctx: Any) -> None: ...

    async def send_mail(self, kind: MailTemplateKind, user: User, **extra_ctx: Any) -> None: ...


# Each rule takes the concrete event type it is registered for, so the shared
# value type has to accept any event.
NotificationRule = Callable[[NotificationSender, Any, str], Awaitable[None]]
