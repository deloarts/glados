"""
Read-only audit trail. No POST/PATCH/DELETE: jobs are written only by
PrintDocument.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User
from src.modules.quality.adapters.inbound.api.deps.printing import get_print_jobs_use_case
from src.modules.quality.adapters.inbound.api.schemas.print_template_schema import (
    PrintJobFilterParams,
)
from src.modules.quality.adapters.inbound.api.schemas.print_template_schema import PrintJobResponse
from src.modules.quality.application.dto.print_template_dto import PrintJobResult
from src.modules.quality.application.use_cases.print_document.get_print_jobs import GetPrintJobs

router = APIRouter()


@router.get("/", response_model=PageResponse[PrintJobResponse])
async def read_print_jobs(
    params: PrintJobFilterParams = Depends(),
    actor: User = Depends(get_current_active_user),
    use_case: GetPrintJobs = Depends(get_print_jobs_use_case),
) -> PageResponse[PrintJobResult]:
    """List print jobs (the print audit trail). Requires read:settings."""
    result = await use_case.execute(actor, params.to_dto())
    return PageResponse.from_result(result, params)
