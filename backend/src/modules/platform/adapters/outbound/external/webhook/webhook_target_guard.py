"""
The webhook target policy. A URL passes when it is plain http or https
without credentials, its host is not one of the stack's own service names
or localhost, and every address the host resolves to is allowed.

Always refused, whatever the settings say: loopback, link-local (which
covers the 169.254.169.254 cloud metadata address and fe80::/10),
unspecified and the 0.0.0.0/8 "this network" block, multicast, reserved
ranges, the IPv4-mapped IPv6 forms of all of these, and the subnets of the
stack's own networks (NETWORK__INTERNAL_SUBNETS). Private ranges such as
RFC 1918 and unique local IPv6 pass unless the admin setting that allows
them is off, since another host on the company network is a normal webhook
receiver for an internal system.

Every resolved address must pass, not just the first, so a hostname cannot
hide a forbidden address behind an allowed one and rely on the client
falling back to it.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sequence
from ipaddress import IPv4Address
from ipaddress import IPv4Network
from ipaddress import IPv6Address
from ipaddress import IPv6Network

import httpx

from src.modules.platform.domain.exceptions import InvalidWebhookConfigurationError
from src.modules.platform.domain.services.stack_hosts import is_always_refused_address
from src.modules.platform.domain.services.stack_hosts import is_stack_host
from src.modules.platform.ports.outbound.webhook_target_guard_port import WebhookTarget

_RESOLVE_TIMEOUT_SECONDS = 5.0

Resolver = Callable[[str, int], Awaitable[Sequence[str]]]


async def _system_resolve(host: str, port: int) -> list[str]:
    """Every A and AAAA answer for `host`, without duplicates, in resolver
    order. The lookup runs in the event loop's executor, so it never blocks
    the loop."""
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses: list[str] = []
    for _family, _type, _proto, _canonname, sockaddr in infos:
        address = str(sockaddr[0])
        if address not in addresses:
            addresses.append(address)
    return addresses


class WebhookTargetGuard:
    def __init__(
        self,
        internal_subnets: Sequence[IPv4Network | IPv6Network] = (),
        *,
        resolver: Resolver | None = None,
        resolve_timeout_seconds: float = _RESOLVE_TIMEOUT_SECONDS,
    ) -> None:
        self._internal_subnets = tuple(internal_subnets)
        self._resolver = resolver or _system_resolve
        self._resolve_timeout = resolve_timeout_seconds

    async def resolve(self, url: str, *, allow_private: bool) -> WebhookTarget:
        parsed = _parse(url)
        host = parsed.raw_host.decode("ascii").rstrip(".").lower()
        if not host:
            raise InvalidWebhookConfigurationError("Webhook URL has no host.")
        # Refused by name as well, which also covers a stack started without
        # NETWORK__INTERNAL_SUBNETS.
        if is_stack_host(host):
            raise _always_refused(host)

        addresses = await self._addresses_of(host, parsed.port or _default_port(parsed))
        for address in addresses:
            ip = _unmapped(ipaddress.ip_address(address.split("%", 1)[0]))
            if self._always_refused(ip):
                raise _always_refused(host)
            if not allow_private and not ip.is_global:
                raise InvalidWebhookConfigurationError(
                    f"Webhook host {host!r} is on a private network, and Admin Settings → "
                    "Features → Allow private webhook targets is off."
                )
        return WebhookTarget(host=host, addresses=tuple(addresses))

    async def _addresses_of(self, host: str, port: int) -> list[str]:
        try:
            return [str(ipaddress.ip_address(host))]
        except ValueError:
            pass
        try:
            async with asyncio.timeout(self._resolve_timeout):
                addresses = list(await self._resolver(host, port))
        except (OSError, TimeoutError):
            addresses = []
        if not addresses:
            raise InvalidWebhookConfigurationError(f"Webhook host {host!r} could not be resolved.")
        return addresses

    def _always_refused(self, ip: IPv4Address | IPv6Address) -> bool:
        return is_always_refused_address(ip, self._internal_subnets)


def _parse(url: str) -> httpx.URL:
    try:
        parsed = httpx.URL(url)
    except (httpx.InvalidURL, TypeError, ValueError) as exc:
        raise InvalidWebhookConfigurationError(f"Webhook URL {url!r} is not a valid URL.") from exc
    if parsed.port is not None and not 0 < parsed.port < 65536:
        raise InvalidWebhookConfigurationError(f"Webhook URL {url!r} is not a valid URL.")
    if parsed.scheme not in ("http", "https"):
        raise InvalidWebhookConfigurationError(
            f"Webhook URL must start with http:// or https://, got {url!r}."
        )
    if parsed.userinfo:
        raise InvalidWebhookConfigurationError(
            "Webhook URL must not carry a user name or password; the signature authenticates "
            "the delivery."
        )
    return parsed


def _default_port(parsed: httpx.URL) -> int:
    return 443 if parsed.scheme == "https" else 80


def _unmapped(ip: IPv4Address | IPv6Address) -> IPv4Address | IPv6Address:
    """The IPv4 address inside an IPv4-mapped IPv6 address, which reaches
    the same host as the IPv4 address itself."""
    if isinstance(ip, IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def _always_refused(host: str) -> InvalidWebhookConfigurationError:
    return InvalidWebhookConfigurationError(
        f"Webhook host {host!r} points at an address Glados never sends webhooks to: the local "
        "host, a link-local or cloud metadata address, a multicast or reserved range, or the "
        "Glados stack's own network and services."
    )
