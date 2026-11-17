"""Use cases for retrieving printer(s) by ID or with filters."""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.quality.application.dto.printer_dto import PrinterResult
from src.modules.quality.application.mappers.printer_mapper import PrinterMapper
from src.modules.quality.domain.errors import PrinterNotFoundError
from src.modules.quality.ports.outbound.repositories.printer_repository import IPrinterRepository
from src.modules.quality.ports.outbound.repositories.printer_repository import PrinterFilterDto


class PaginatedPrinters:
    def __init__(self, total: int, items: list[PrinterResult]):
        self.total = total
        self.items = items


class GetPrinter:
    def __init__(self, printer_repo: IPrinterRepository) -> None:
        self._printers = printer_repo

    async def execute(self, printer_id: int) -> PrinterResult:
        printer = found_or_raise(
            await self._printers.get_by_id(printer_id),
            PrinterNotFoundError,
            f"Printer #{printer_id} not found.",
        )
        return PrinterMapper.to_result(printer)


class GetPrinters:
    def __init__(self, printer_repo: IPrinterRepository) -> None:
        self._printers = printer_repo

    async def execute(self, filters: PrinterFilterDto) -> PaginatedPrinters:
        total, items = await self._printers.get_multi(filters)
        return PaginatedPrinters(total=total, items=[PrinterMapper.to_result(i) for i in items])
