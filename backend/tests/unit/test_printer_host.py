"""Which hosts a printer may point at (quality/domain/services/printer_host.py)."""

import pytest

from src.modules.quality.domain.errors import InvalidPrinterHostError
from src.modules.quality.domain.services.printer_host import printer_host_problem
from src.modules.quality.domain.services.printer_rules import PrinterRules


@pytest.mark.parametrize(
    "host", ["192.168.10.40", "zebra-hall2", "printer.factory.example.com", "fd00::40", "10.0.0.9"]
)
def test_printers_on_the_network_are_accepted(host: str) -> None:
    assert printer_host_problem(host) is None


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "::1",
        "169.254.169.254",
        "0.0.0.0",
        "0.1.2.3",
        "224.0.0.1",
        "::ffff:127.0.0.1",
        "localhost",
        "printer.localhost",
        "postgres",
        "Redis",
        "backend.",
    ],
)
def test_the_server_itself_and_the_stack_are_refused(host: str) -> None:
    assert printer_host_problem(host) is not None


@pytest.mark.parametrize(
    "host", ["evil@10.0.0.1", "10.0.0.1/admin", "host:9100", "a b", "", "-printer", "x" * 254]
)
def test_anything_but_a_host_name_or_address_is_refused(host: str) -> None:
    assert printer_host_problem(host) is not None


def test_the_rule_raises_the_invalid_host_error() -> None:
    with pytest.raises(InvalidPrinterHostError):
        PrinterRules.assert_host_allowed("localhost")
