"""
The scrap tag print of a production lot, under the lot routes' path
(/production-lots/{lot_id}/print). Printing is Quality & documents' job, so
the route lives here; the web router mounts it next to the lot routes.
"""

from fastapi import Depends
from fastapi.routing import APIRouter
from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User
from src.modules.quality.adapters.inbound.api.deps.printing import get_print_lot_scrap_tag_use_case
from src.modules.quality.adapters.inbound.api.schemas.print_template_schema import PrintJobResponse
from src.modules.quality.application.dto.print_template_dto import PrintJobResult
from src.modules.quality.application.use_cases.print_document.print_lot_scrap_tag import (
    PrintLotScrapTag,
)

router = APIRouter()


class ScrapTagPrintRequest(BaseModel):
    """Body for POST /production-lots/{id}/print. Optional overrides for
    the scrap_tag classifier's configured printer/copies, same fields as a
    generic PrintRequestItemRequest, minus `classifier` (fixed)."""

    printer_id: int | None = None
    copies: int | None = Field(default=None, ge=1)


@router.post("/{lot_id}/print", response_model=PrintJobResponse)
async def print_lot_scrap_tag(
    lot_id: int,
    body: ScrapTagPrintRequest,
    actor: User = Depends(get_current_active_user),
    use_case: PrintLotScrapTag = Depends(get_print_lot_scrap_tag_use_case),
) -> PrintJobResult:
    """Manual scrap tag print scoped to a lot: the lot context menu's
    "Scrap tag" entry. Unlike every other classifier's manual print
    (POST /print, root_type + root_id supplied by the caller), the scrap
    tag's root is a completion or delivery record the frontend has no way
    to name; the use case resolves the lot's own latest scrap record
    itself."""
    return await use_case.execute(actor, lot_id, printer_id=body.printer_id, copies=body.copies)
