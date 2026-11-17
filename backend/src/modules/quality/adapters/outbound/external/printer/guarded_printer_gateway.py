"""
Checks where a printer's host actually leads before any connection is
opened. The host was only checked as text when it was saved
(printer_host.py), so a name that resolves to the server itself, to a
container of the stack or to the cloud metadata address would otherwise
still be reached, and its reply shown to the caller.

Every address the host resolves to must pass, not just the first, so a
name cannot hide a refused address behind an allowed one. The connection
then goes to the first checked address rather than the name, so a second
lookup cannot answer differently. Private ranges pass, since a printer is
another host on the company network.
"""

import asyncio
import socket
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import replace
from ipaddress import IPv4Network
from ipaddress import IPv6Network

from src.modules.platform.domain.services.stack_hosts import is_always_refused_address
from src.modules.platform.domain.services.stack_hosts import is_stack_host
from src.modules.platform.domain.services.stack_hosts import parse_address
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.errors import InvalidPrinterHostError
from src.modules.quality.domain.errors import PrinterUnreachableError
from src.modules.quality.domain.value_objects.print_classifier import PrintSides
from src.modules.quality.ports.outbound.printer_gateway_port import IPrinterGateway
from src.modules.quality.ports.outbound.printer_gateway_port import PrintDelivery

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


class GuardedPrinterGateway:
    """Implements IPrinterGateway around another gateway, handing it the
    printer with its host replaced by the checked address."""

    def __init__(
        self,
        inner: IPrinterGateway,
        internal_subnets: Sequence[IPv4Network | IPv6Network] = (),
        *,
        resolver: Resolver | None = None,
    ) -> None:
        self._inner = inner
        self._internal_subnets = tuple(internal_subnets)
        self._resolver = resolver or _system_resolve

    async def send(
        self,
        printer: Printer,
        payload: bytes,
        content_type: str,
        copies: int,
        *,
        sides: PrintSides = PrintSides.ONE_SIDED,
    ) -> PrintDelivery:
        target = await self._checked(printer)
        return await self._inner.send(target, payload, content_type, copies, sides=sides)

    async def identify(self, printer: Printer) -> str:
        return await self._inner.identify(await self._checked(printer))

    async def status(self, printer: Printer) -> list[str]:
        return await self._inner.status(await self._checked(printer))

    async def _checked(self, printer: Printer) -> Printer:
        host = printer.host.strip().rstrip(".").lower()
        if is_stack_host(host):
            raise InvalidPrinterHostError(f"{printer.host} is a service of the Glados stack.")
        addresses = await self._addresses_of(printer, host)
        for address in addresses:
            if is_always_refused_address(parse_address(address), self._internal_subnets):
                raise InvalidPrinterHostError(
                    f"{printer.host} leads to an address a printer cannot have."
                )
        return replace(printer, host=addresses[0])

    async def _addresses_of(self, printer: Printer, host: str) -> list[str]:
        try:
            return [str(parse_address(host))]
        except ValueError:
            pass
        try:
            async with asyncio.timeout(printer.timeout_seconds):
                addresses = list(await self._resolver(host, printer.port))
        except (OSError, TimeoutError):
            addresses = []
        if not addresses:
            raise PrinterUnreachableError(f"{printer.host} could not be resolved.")
        return addresses
