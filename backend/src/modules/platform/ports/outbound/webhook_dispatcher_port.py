"""
Abstract HTTP delivery of one webhook payload. The application layer decides
what to send and to whom; the implementation owns HTTP, timeouts, the
signature headers and the check of the target address right before sending.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable


@dataclass(frozen=True)
class WebhookDispatchResult:
    http_status: int | None  # None when the request itself failed (DNS, timeout, ...)
    duration_ms: int
    error: str | None


@runtime_checkable
class IWebhookDispatcher(Protocol):
    async def post(
        self,
        *,
        url: str,
        secret: str,
        event_type: str,
        delivery_id: str,
        payload: str,
        allow_private: bool,
        timeout_seconds: float | None = None,
    ) -> WebhookDispatchResult:
        """POST `payload` (a JSON document) to `url`. Must not raise,
        transport failures are reported via the result's error field.

        The target is checked again before every delivery (see
        IWebhookTargetGuard), and a refused one fails the delivery without
        a request. `allow_private` is the admin setting
        `features.allow_private_webhooks`, read fresh by the caller.

        `timeout_seconds`, when given, overrides the dispatcher's own
        constructor default for this call only. See
        DispatchEventToWebhooks, which reads the admin-configured
        `notifications.webhook_timeout_seconds` fresh on every dispatch and
        passes it here, so the long-lived worker's dispatcher instance never
        needs rebuilding when an admin changes the setting. None keeps
        whatever the implementation already defaults to.
        """
        ...
