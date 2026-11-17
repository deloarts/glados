"""
Abstract printer transport. The application layer calls this, never the
raw-socket or IPP implementation directly. Two adapters exist, selected by
Printer.kind: ZplSocketPrinterGateway (raw TCP 9100) and
IppDocumentPrinterGateway (IPP 631). Both wrap connection failures into
PrinterUnreachableError and rejected jobs into PrintRejectedError.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable

from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.value_objects.print_classifier import PrintSides


@dataclass(frozen=True)
class PrintDelivery:
    """What the printer said on accepting a job. `attributes_substituted`
    is set when it took the job but not every requested setting, such as
    two-sided output on a printer without a duplex unit, or any setting at
    all on a raw connection, which cannot carry one."""

    attributes_substituted: bool = False


@runtime_checkable
class IPrinterGateway(Protocol):
    async def send(
        self,
        printer: Printer,
        payload: bytes,
        content_type: str,
        copies: int,
        *,
        sides: PrintSides = PrintSides.ONE_SIDED,
    ) -> PrintDelivery:
        """Send a rendered document to the printer. `sides` applies to IPP
        document printers only. Raises PrinterUnreachableError or
        PrintRejectedError on failure."""
        ...

    async def identify(self, printer: Printer) -> str:
        """Query the printer for model/firmware/capabilities. Prints nothing."""
        ...

    async def status(self, printer: Printer) -> list[str]:
        """Query the printer's current status (paper out, paused, ...). Prints
        nothing."""
        ...
