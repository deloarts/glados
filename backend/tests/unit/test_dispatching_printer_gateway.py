"""
Unit tests for DispatchingPrinterGateway's kind-based routing. No real
sockets: the concrete gateways it dispatches to fail fast on an unroutable
host, which is enough to prove routing without a printer present.
"""

from datetime import date
from enum import Enum

import pytest

from src.modules.quality.adapters.outbound.external.printer.dispatching_printer_gateway import (
    DispatchingPrinterGateway,
)
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.errors import PrinterKindMismatchError
from src.modules.quality.domain.errors import PrinterUnreachableError
from src.modules.quality.domain.value_objects.printer_kind import PrinterKind


def make_printer(kind: PrinterKind) -> Printer:
    return Printer(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=False,
        name="Test Printer",
        internal_name="test-printer",
        kind=kind,
        host="127.0.0.1",
        port=1,  # nothing listens here, connection refuses immediately
        timeout_seconds=0.2,
        transport="raw" if kind == "zpl_label" else "ipp",
        ipp_uri_path="/",
        head_dpi=300,
        format_convert_factor=2,
        default_media=None,
        location=None,
        vendor=None,
        model=None,
        firmware=None,
        bought_item_ids=[],
        enabled=True,
        is_default=False,
        note=None,
        creator_id=1,
    )


class _UnregisteredKind(str, Enum):
    """A printer kind no gateway is registered for, which PrinterKind
    itself never names."""

    DOT_MATRIX = "dot_matrix"


async def test_unknown_kind_raises_kind_mismatch():
    gateway = DispatchingPrinterGateway()
    printer = make_printer(kind=_UnregisteredKind.DOT_MATRIX)  # type: ignore[arg-type]

    with pytest.raises(PrinterKindMismatchError):
        await gateway.send(printer, b"payload", "text/plain", copies=1)


async def test_zpl_kind_dispatches_to_socket_gateway_and_fails_unreachable():
    gateway = DispatchingPrinterGateway()
    printer = make_printer(kind=PrinterKind.ZPL_LABEL)

    with pytest.raises(PrinterUnreachableError):
        await gateway.send(printer, b"^XA^XZ", "application/x-zpl", copies=1)


async def test_ipp_kind_dispatches_to_ipp_gateway_and_fails_unreachable():
    gateway = DispatchingPrinterGateway()
    printer = make_printer(kind=PrinterKind.IPP_DOCUMENT)

    with pytest.raises(PrinterUnreachableError):
        await gateway.send(printer, b"%PDF-1.4", "application/pdf", copies=1)
