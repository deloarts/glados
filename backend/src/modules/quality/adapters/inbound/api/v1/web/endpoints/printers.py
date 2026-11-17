"""
Printer catalogue endpoints. Prefix `/printers`.
"""

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User
from src.modules.quality.adapters.inbound.api.deps.printing import get_archive_printer_use_case
from src.modules.quality.adapters.inbound.api.deps.printing import get_create_printer_use_case
from src.modules.quality.adapters.inbound.api.deps.printing import get_printer_status_use_case
from src.modules.quality.adapters.inbound.api.deps.printing import get_printer_use_case
from src.modules.quality.adapters.inbound.api.deps.printing import get_printers_use_case
from src.modules.quality.adapters.inbound.api.deps.printing import get_restore_printer_use_case
from src.modules.quality.adapters.inbound.api.deps.printing import get_test_print_printer_use_case
from src.modules.quality.adapters.inbound.api.deps.printing import get_update_printer_use_case
from src.modules.quality.adapters.inbound.api.schemas.printer_schema import PrinterCreateRequest
from src.modules.quality.adapters.inbound.api.schemas.printer_schema import PrinterFilterParams
from src.modules.quality.adapters.inbound.api.schemas.printer_schema import PrinterResponse
from src.modules.quality.adapters.inbound.api.schemas.printer_schema import PrinterStatusResponse
from src.modules.quality.adapters.inbound.api.schemas.printer_schema import PrinterUpdateRequest
from src.modules.quality.application.dto.printer_dto import CreatePrinterCommand
from src.modules.quality.application.dto.printer_dto import PrinterResult
from src.modules.quality.application.dto.printer_dto import PrinterStatusResult
from src.modules.quality.application.dto.printer_dto import UpdatePrinterCommand
from src.modules.quality.application.use_cases.printer.archive_printer import ArchivePrinter
from src.modules.quality.application.use_cases.printer.create_printer import CreatePrinter
from src.modules.quality.application.use_cases.printer.get_printer import GetPrinter
from src.modules.quality.application.use_cases.printer.get_printer import GetPrinters
from src.modules.quality.application.use_cases.printer.get_printer_status import GetPrinterStatus
from src.modules.quality.application.use_cases.printer.restore_printer import RestorePrinter
from src.modules.quality.application.use_cases.printer.test_print_printer import TestPrintPrinter
from src.modules.quality.application.use_cases.printer.update_printer import UpdatePrinter

router = APIRouter()


@router.get("/", response_model=PageResponse[PrinterResponse])
async def read_printers(
    params: PrinterFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    use_case: GetPrinters = Depends(get_printers_use_case),
) -> PageResponse[PrinterResult]:
    result = await use_case.execute(params.to_dto())
    return PageResponse.from_result(result, params)


@router.post("/", response_model=PrinterResponse, status_code=status.HTTP_201_CREATED)
async def create_printer(
    body: PrinterCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreatePrinter = Depends(get_create_printer_use_case),
) -> PrinterResult:
    cmd = CreatePrinterCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.get("/{printer_id}", response_model=PrinterResponse)
async def read_printer(
    printer_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetPrinter = Depends(get_printer_use_case),
) -> PrinterResult:
    return await use_case.execute(printer_id=printer_id)


@router.patch("/{printer_id}", response_model=PrinterResponse)
async def update_printer(
    printer_id: int,
    body: PrinterUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdatePrinter = Depends(get_update_printer_use_case),
) -> PrinterResult:
    cmd = UpdatePrinterCommand(**body.model_dump())
    return await use_case.execute(actor=actor, printer_id=printer_id, cmd=cmd)


@router.post("/{printer_id}/archive", response_model=PrinterResponse)
async def archive_printer(
    printer_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ArchivePrinter = Depends(get_archive_printer_use_case),
) -> PrinterResult:
    return await use_case.execute(actor=actor, printer_id=printer_id)


@router.post("/{printer_id}/restore", response_model=PrinterResponse)
async def restore_printer(
    printer_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RestorePrinter = Depends(get_restore_printer_use_case),
) -> PrinterResult:
    return await use_case.execute(actor=actor, printer_id=printer_id)


@router.post("/{printer_id}/test-print", status_code=status.HTTP_204_NO_CONTENT)
async def test_print_printer(
    printer_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: TestPrintPrinter = Depends(get_test_print_printer_use_case),
) -> None:
    """Send a built-in self-test job. Requires print:documents."""
    await use_case.execute(actor=actor, printer_id=printer_id)


@router.get("/{printer_id}/status", response_model=PrinterStatusResponse)
async def read_printer_status(
    printer_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetPrinterStatus = Depends(get_printer_status_use_case),
) -> PrinterStatusResult:
    """Query the printer for identity + status. Prints nothing. Requires
    print:documents."""
    return await use_case.execute(actor=actor, printer_id=printer_id)
