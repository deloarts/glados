"""
Routes to the concrete gateway matching Printer.kind. Implements
IPrinterGateway itself, so use cases depend on one gateway regardless of how
many printer kinds exist, adding a third kind later is a dict entry here,
not a new use-case constructor parameter.
"""

from src.modules.quality.adapters.outbound.external.printer.ipp_document_printer_gateway import (
    IppDocumentPrinterGateway,
)
from src.modules.quality.adapters.outbound.external.printer.zpl_socket_printer_gateway import (
    ZplSocketPrinterGateway,
)
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.errors import PrinterKindMismatchError
from src.modules.quality.domain.value_objects.print_classifier import PrintSides
from src.modules.quality.ports.outbound.printer_gateway_port import IPrinterGateway
from src.modules.quality.ports.outbound.printer_gateway_port import PrintDelivery


class DispatchingPrinterGateway:
    """Implements IPrinterGateway, dispatching on printer.kind."""

    def __init__(self) -> None:
        self._gateways: dict[str, IPrinterGateway] = {
            "zpl_label": ZplSocketPrinterGateway(),
            "ipp_document": IppDocumentPrinterGateway(),
        }

    def _resolve(self, printer: Printer) -> IPrinterGateway:
        gateway = self._gateways.get(printer.kind)
        if gateway is None:
            raise PrinterKindMismatchError(
                f"No gateway registered for printer kind {printer.kind.value!r}."
            )
        return gateway

    async def send(
        self,
        printer: Printer,
        payload: bytes,
        content_type: str,
        copies: int,
        *,
        sides: PrintSides = PrintSides.ONE_SIDED,
    ) -> PrintDelivery:
        return await self._resolve(printer).send(
            printer, payload, content_type, copies, sides=sides
        )

    async def identify(self, printer: Printer) -> str:
        return await self._resolve(printer).identify(printer)

    async def status(self, printer: Printer) -> list[str]:
        return await self._resolve(printer).status(printer)
