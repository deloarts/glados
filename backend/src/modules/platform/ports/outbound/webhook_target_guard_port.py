"""
Decides whether a webhook URL may be called and which address to call it
on. A webhook URL is chosen by an administrator, so without this check a
subscription could make the worker send requests to the stack's own
services, the host itself or a cloud metadata endpoint.

The guard runs when a subscription is created or edited and again before
every delivery, because what a hostname resolves to can change in between.
The delivery then connects to one of the addresses the guard returned, so
a second, different DNS answer cannot slip in between the check and the
request.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable


@dataclass(frozen=True)
class WebhookTarget:
    """A URL that passed the guard. `host` is the hostname in its ASCII
    form, as sent in the Host header and used for TLS, and `addresses`
    holds every address it resolved to, all of them allowed, in the order
    the resolver returned them."""

    host: str
    addresses: tuple[str, ...]


@runtime_checkable
class IWebhookTargetGuard(Protocol):
    async def resolve(self, url: str, *, allow_private: bool) -> WebhookTarget:
        """Check `url` and resolve its host. Raises
        InvalidWebhookConfigurationError when the URL is malformed, its
        host cannot be resolved, or any address it resolves to is one
        Glados never sends to. `allow_private` lets private ranges (RFC
        1918, unique local IPv6 and the like) through; the always refused
        set stays refused either way. The error message names the host but
        never a resolved address, so it reveals nothing about the internal
        network."""
        ...
