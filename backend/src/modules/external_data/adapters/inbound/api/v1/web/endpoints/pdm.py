"""
Catalogue-facing PDM endpoints, distinct from the admin "PDM files"
pending list under /admin/settings/pdm/files (write:settings) and from
the API-key/PAT surfaces under v1/key and v1/pat. GET /preview backs the
made/bought catalogue's "PDM preview" panel: files the vault has that
Glados hasn't (fully) ingested yet.
"""

from typing import Literal

from fastapi import Depends
from fastapi import Query
from fastapi.routing import APIRouter

from src.modules.external_data.adapters.inbound.api.deps.pdm import get_list_pdm_preview_use_case
from src.modules.external_data.adapters.inbound.api.schemas.pdm_preview_schema import (
    PdmPreviewResponse,
)
from src.modules.external_data.application.use_cases.pdm.list_pdm_preview import ListPdmPreview
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/preview", response_model=PdmPreviewResponse)
async def read_pdm_preview(
    kind: Literal["made", "bought"] = Query(...),
    actor: User = Depends(get_current_active_user),
    use_case: ListPdmPreview = Depends(get_list_pdm_preview_use_case),
) -> PdmPreviewResponse:
    """Files PDM has for `kind` that Glados hasn't fully caught up with:
    `unlinked` (no Glados row at all) and `newer` (a linked item behind
    the vault's latest release). `enabled` is false, with both lists
    empty, whenever the PDM integration is off or unconfigured. This is
    never an error, so the UI can simply hide the preview button."""
    result = await use_case.execute(actor, kind)
    return PdmPreviewResponse.model_validate(result.model_dump())
