"""Use case for querying the live status of a printer via its gateway."""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.quality.application.dto.printer_dto import PrinterStatusResult
from src.modules.quality.domain.errors import PrinterNotFoundError
from src.modules.quality.domain.services.printer_rules import PrinterRules
from src.modules.quality.ports.outbound.printer_gateway_port import IPrinterGateway
from src.modules.quality.ports.outbound.repositories.printer_repository import IPrinterRepository


class GetPrinterStatus:
    def __init__(self, printer_repo: IPrinterRepository, *, gateway: IPrinterGateway) -> None:
        self._printers = printer_repo
        self._gateway = gateway

    async def execute(self, actor: User, printer_id: int) -> PrinterStatusResult:
        PrinterRules.assert_can_print(actor)

        printer = found_or_raise(
            await self._printers.get_by_id(printer_id),
            PrinterNotFoundError,
            f"Printer #{printer_id} not found.",
        )

        return PrinterStatusResult(
            identity=await self._gateway.identify(printer),
            status_lines=await self._gateway.status(printer),
        )
