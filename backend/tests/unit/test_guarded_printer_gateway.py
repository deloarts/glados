"""
Unit tests for GuardedPrinterGateway: where a printer's host leads is
checked before the inner gateway opens a connection, and the inner gateway
is handed the checked address rather than the name.
"""

from collections.abc import Sequence
from dataclasses import replace
from ipaddress import IPv4Network

import pytest

from src.modules.quality.adapters.outbound.external.printer.guarded_printer_gateway import (
    GuardedPrinterGateway,
)
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.errors import InvalidPrinterHostError
from src.modules.quality.domain.errors import PrinterUnreachableError
from src.modules.quality.domain.value_objects.print_classifier import PrintSides
from src.modules.quality.domain.value_objects.printer_kind import PrinterKind
from src.modules.quality.ports.outbound.printer_gateway_port import PrintDelivery
from tests.unit.test_dispatching_printer_gateway import make_printer


class RecordingGateway:
    def __init__(self) -> None:
        self.hosts: list[str] = []

    async def send(
        self,
        printer: Printer,
        payload: bytes,
        content_type: str,
        copies: int,
        *,
        sides: PrintSides = PrintSides.ONE_SIDED,
    ) -> PrintDelivery:
        self.hosts.append(printer.host)
        raise AssertionError("send is not exercised here")

    async def identify(self, printer: Printer) -> str:
        self.hosts.append(printer.host)
        return "ZT230"

    async def status(self, printer: Printer) -> list[str]:
        self.hosts.append(printer.host)
        return ["ok"]


def _resolving_to(*addresses: str):
    async def resolve(host: str, port: int) -> Sequence[str]:
        return list(addresses)

    return resolve


def _printer(host: str) -> Printer:
    return replace(make_printer(PrinterKind.ZPL_LABEL), host=host)


async def test_a_name_on_the_network_is_reached_by_its_checked_address():
    inner = RecordingGateway()
    gateway = GuardedPrinterGateway(inner, resolver=_resolving_to("10.20.0.7"))

    assert await gateway.identify(_printer("zebra-1.example.com")) == "ZT230"
    assert inner.hosts == ["10.20.0.7"]


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "::1", "169.254.169.254", "0.0.0.5", "::ffff:127.0.0.1"]
)
async def test_a_name_leading_to_the_server_itself_is_refused(address):
    inner = RecordingGateway()
    gateway = GuardedPrinterGateway(inner, resolver=_resolving_to(address))

    with pytest.raises(InvalidPrinterHostError):
        await gateway.status(_printer("printer.example.com"))
    assert inner.hosts == []


async def test_one_refused_address_among_allowed_ones_is_refused():
    gateway = GuardedPrinterGateway(
        RecordingGateway(), resolver=_resolving_to("10.20.0.7", "127.0.0.1")
    )

    with pytest.raises(InvalidPrinterHostError):
        await gateway.status(_printer("printer.example.com"))


async def test_an_address_in_the_stacks_own_network_is_refused():
    gateway = GuardedPrinterGateway(
        RecordingGateway(),
        [IPv4Network("172.30.0.0/16")],
        resolver=_resolving_to("172.30.0.4"),
    )

    with pytest.raises(InvalidPrinterHostError):
        await gateway.status(_printer("sneaky.example.com"))


async def test_a_stack_service_name_is_refused_without_a_lookup():
    async def resolve(host: str, port: int) -> Sequence[str]:
        raise AssertionError("not looked up")

    gateway = GuardedPrinterGateway(RecordingGateway(), resolver=resolve)

    with pytest.raises(InvalidPrinterHostError):
        await gateway.status(_printer("postgres"))


async def test_an_ip_literal_is_checked_without_a_lookup():
    async def resolve(host: str, port: int) -> Sequence[str]:
        raise AssertionError("not looked up")

    inner = RecordingGateway()
    gateway = GuardedPrinterGateway(inner, resolver=resolve)

    await gateway.status(_printer("192.168.1.50"))
    assert inner.hosts == ["192.168.1.50"]
    with pytest.raises(InvalidPrinterHostError):
        await gateway.status(_printer("127.0.0.1"))


async def test_a_name_that_does_not_resolve_is_unreachable():
    async def resolve(host: str, port: int) -> Sequence[str]:
        raise OSError("Name or service not known")

    gateway = GuardedPrinterGateway(RecordingGateway(), resolver=resolve)

    with pytest.raises(PrinterUnreachableError):
        await gateway.status(_printer("gone.example.com"))
