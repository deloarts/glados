"""
Delivers one webhook payload via httpx, signed the Standard Webhooks way
(https://www.standardwebhooks.com) so receivers can verify both who sent it
and when:

    webhook-id:        <event bus message ID, the same on every retry>
    webhook-timestamp: <Unix seconds at sending>
    webhook-signature: v1,<base64 HMAC-SHA256 of "{id}.{timestamp}.{body}">
    X-Glados-Event:    <event class name>

The HMAC key is the subscription secret with its `whsec_` prefix removed,
base64-decoded, which is what the Standard Webhooks libraries do, so a
receiver can verify with one of them or by hand. Covering the timestamp
lets a receiver refuse a captured delivery replayed later.

Before sending, the target guard checks the URL and resolves its host, and
the request goes to the first address it returned. The Host header and the
TLS server name stay the hostname, so certificate verification still
checks the hostname and not the address. Redirects are not followed, since
a redirect could point anywhere the guard would have refused.

Never raises, failures come back in the result's error field so the caller
can log the attempt either way. Only the response status is used; the body
is never read. The error text is a short category, never the raw exception,
so the delivery log reveals nothing a refused or internal host answered.
"""

import base64
import binascii
import hashlib
import hmac
import ssl
import time

import httpx

from src.modules.platform.domain.exceptions import InvalidWebhookConfigurationError
from src.modules.platform.ports.outbound.webhook_dispatcher_port import WebhookDispatchResult
from src.modules.platform.ports.outbound.webhook_target_guard_port import IWebhookTargetGuard
from src.shared_kernel.domain.services.clock import now_utc

_TIMEOUT_SECONDS = 10.0
_SECRET_PREFIX = "whsec_"


def sign_payload(secret: str, message_id: str, timestamp: int, payload: str) -> str:
    """The `webhook-signature` header value for one delivery. Raises
    ValueError when the secret is not valid base64."""
    try:
        key = base64.b64decode(secret.removeprefix(_SECRET_PREFIX), validate=True)
    except binascii.Error as exc:
        raise ValueError("The signing secret is not valid base64.") from exc
    if not key:
        raise ValueError("The signing secret is empty.")
    signed = f"{message_id}.{timestamp}.{payload}".encode()
    digest = hmac.new(key, signed, hashlib.sha256).digest()
    return f"v1,{base64.b64encode(digest).decode()}"


class HttpxWebhookDispatcher:
    def __init__(
        self,
        target_guard: IWebhookTargetGuard,
        timeout_seconds: float = _TIMEOUT_SECONDS,
        *,
        verify: ssl.SSLContext | bool = True,
    ) -> None:
        self._guard = target_guard
        self._timeout = timeout_seconds
        self._verify = verify

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
        # Empty when the stored secret could not be decrypted (see
        # persistence/encrypted_type.py). An unsigned or empty-key delivery
        # would only be rejected by the receiver, so record why instead.
        if not secret:
            return _failed(
                "Signing secret is unreadable, check SECURITY__ENCRYPTION_KEY"
                " or recreate the subscription."
            )
        timestamp = int(now_utc().timestamp())
        try:
            signature = sign_payload(secret, delivery_id, timestamp, payload)
        except ValueError:
            return _failed("Signing secret is malformed, recreate the subscription.")

        start = time.perf_counter()
        try:
            target = await self._guard.resolve(url, allow_private=allow_private)
        except InvalidWebhookConfigurationError as exc:
            # Refused targets never receive a request.
            return _failed(f"Refused: {exc}", start)

        original = httpx.URL(url)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Glados-Webhook",
            "Host": original.netloc.decode("ascii"),
            "webhook-id": delivery_id,
            "webhook-timestamp": str(timestamp),
            "webhook-signature": signature,
            "X-Glados-Event": event_type,
        }
        pinned = original.copy_with(host=target.addresses[0])
        # Per-call override wins, so an admin-configured timeout takes effect
        # on the very next dispatch, no rebuild of this long-lived instance.
        timeout = timeout_seconds if timeout_seconds is not None else self._timeout

        try:
            # Streamed and closed without reading the body: only the status
            # matters, and a receiver must not be able to make this worker
            # download an arbitrarily large response.
            async with (
                httpx.AsyncClient(
                    timeout=timeout, verify=self._verify, follow_redirects=False
                ) as client,
                client.stream(
                    "POST",
                    pinned,
                    content=payload,
                    headers=headers,
                    extensions={"sni_hostname": target.host},
                ) as response,
            ):
                status = response.status_code
            return WebhookDispatchResult(
                http_status=status, duration_ms=_elapsed_ms(start), error=None
            )
        except httpx.HTTPError as exc:
            return _failed(_describe(exc), start)


def _describe(exc: httpx.HTTPError) -> str:
    """A short category for a failed request. The raw exception can carry
    text the remote end sent, such as a protocol banner, so it is never
    stored."""
    if isinstance(exc, httpx.TimeoutException):
        return "Timed out."
    if isinstance(exc, httpx.ConnectError):
        if _caused_by_tls(exc):
            return "TLS handshake or certificate verification failed."
        return "Connection failed."
    if isinstance(exc, httpx.RemoteProtocolError | httpx.LocalProtocolError):
        return "The receiver did not answer with valid HTTP."
    return "Request failed."


def _caused_by_tls(exc: BaseException) -> bool:
    seen: set[int] = set()
    cause: BaseException | None = exc
    while cause is not None and id(cause) not in seen:
        if isinstance(cause, ssl.SSLError):
            return True
        seen.add(id(cause))
        cause = cause.__cause__ or cause.__context__
    return False


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _failed(error: str, start: float | None = None) -> WebhookDispatchResult:
    duration_ms = 0 if start is None else _elapsed_ms(start)
    return WebhookDispatchResult(http_status=None, duration_ms=duration_ms, error=error)
