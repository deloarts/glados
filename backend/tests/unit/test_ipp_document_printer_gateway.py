"""
The IPP document gateway puts the requested `sides` into the Print-Job
request and reports a printer that substituted it. The HTTP round trip and
the raw socket are replaced, so no printer is contacted.
"""

from datetime import date

import pytest

from src.modules.quality.adapters.outbound.external.printer import ipp_document_printer_gateway
from src.modules.quality.adapters.outbound.external.printer.ipp_document_printer_gateway import (
    IppDocumentPrinterGateway,
)
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.value_objects.print_classifier import PrintSides
from src.modules.quality.domain.value_objects.printer_kind import PrinterKind


def make_printer(transport: str = "ipp") -> Printer:
    return Printer(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        archived=False,
        name="Office printer",
        internal_name=None,
        kind=PrinterKind.IPP_DOCUMENT,
        host="192.0.2.20",
        port=631,
        timeout_seconds=1.0,
        transport=transport,
        ipp_uri_path="/",
        head_dpi=None,
        format_convert_factor=None,
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


class RecordingGateway(IppDocumentPrinterGateway):
    def __init__(self, status: int) -> None:
        self.bodies: list[bytes] = []
        self._status = status

    async def _post(
        self, printer: Printer, uri: str, body: bytes
    ) -> tuple[int, list[tuple[str, bytes]]]:
        self.bodies.append(body)
        return self._status, []


@pytest.mark.parametrize(
    ("sides", "encoded"),
    [
        (PrintSides.ONE_SIDED, b"one-sided"),
        (PrintSides.TWO_SIDED_LONG_EDGE, b"two-sided-long-edge"),
    ],
)
async def test_ipp_gateway_sends_the_requested_sides(sides: PrintSides, encoded: bytes) -> None:
    gateway = RecordingGateway(status=0x0000)

    delivery = await gateway.send(make_printer(), b"%PDF-1.7", "application/pdf", 1, sides=sides)

    assert b"\x00\x05sides" + len(encoded).to_bytes(2, "big") + encoded in gateway.bodies[0]
    assert delivery.attributes_substituted is False


async def test_ipp_gateway_reports_substituted_attributes() -> None:
    gateway = RecordingGateway(status=0x0001)

    delivery = await gateway.send(
        make_printer(),
        b"%PDF-1.7",
        "application/pdf",
        1,
        sides=PrintSides.TWO_SIDED_LONG_EDGE,
    )

    assert delivery.attributes_substituted is True


async def test_ipp_gateway_raw_transport_cannot_print_two_sided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[bytes] = []

    async def fake_send_raw_tcp(printer: Printer, payload: bytes) -> None:
        sent.append(payload)

    monkeypatch.setattr(ipp_document_printer_gateway, "send_raw_tcp", fake_send_raw_tcp)
    gateway = IppDocumentPrinterGateway()

    one_sided = await gateway.send(make_printer("raw"), b"%PDF-1.7", "application/pdf", 2)
    two_sided = await gateway.send(
        make_printer("raw"),
        b"%PDF-1.7",
        "application/pdf",
        1,
        sides=PrintSides.TWO_SIDED_LONG_EDGE,
    )

    assert sent == [b"%PDF-1.7%PDF-1.7", b"%PDF-1.7"]
    assert one_sided.attributes_substituted is False
    assert two_sided.attributes_substituted is True
