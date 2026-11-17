"""
API-key surface: SolidWorks PDM change-notification trigger, called by a
use:pdm_addin-scoped key holder, such as a Dispatch action, when a file
changes. The vault add-in uses the PAT surface's twin instead
(v1/pat/endpoints/pdm.py). Glados never trusts the payload's own data: it stages a
PdmFileChangeRequested event and re-reads the file from the Web API itself
later, on the pdm_sync worker (see RequestPdmFileRefresh, RefreshPdmFile).

Also the pre-release validation endpoint (docs/reference/pdm-ingest.md
section 8): the same use:pdm_addin scope, but read-only and
synchronous. A vault hook can call it before a release to show the
engineer what ingest would do, see ValidatePdmFile; the vault add-in does
not, since PDM transition conditions guard its releases.

Both have a batch form for an operation that touches many files at once
(POST /files/changed/batch, POST /files/validate/batch), so a caller makes
one call per batch instead of one per file.

Also the trigger config read: the same use:pdm_addin scope, gives a
caller that checks releases itself the vault name and release-state names
without hardcoding them, see GetPdmTriggerConfig.
"""

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.external_data.adapters.inbound.api.deps.pdm import get_pdm_trigger_config_use_case
from src.modules.external_data.adapters.inbound.api.deps.pdm import (
    get_request_pdm_file_refresh_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.pdm import get_validate_pdm_file_use_case
from src.modules.external_data.adapters.inbound.api.schemas.pdm_schema import PdmBatchValidationItem
from src.modules.external_data.adapters.inbound.api.schemas.pdm_schema import (
    PdmBatchValidationRequest,
)
from src.modules.external_data.adapters.inbound.api.schemas.pdm_schema import (
    PdmBatchValidationResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.pdm_schema import PdmFileChangedRequest
from src.modules.external_data.adapters.inbound.api.schemas.pdm_schema import PdmFileChangedResponse
from src.modules.external_data.adapters.inbound.api.schemas.pdm_schema import (
    PdmFilesChangedBatchRequest,
)
from src.modules.external_data.adapters.inbound.api.schemas.pdm_schema import (
    PdmFilesChangedBatchResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.pdm_schema import (
    PdmTriggerConfigResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.pdm_schema import PdmValidationResponse
from src.modules.external_data.application.dto.pdm_dto import PdmChangedFileRef
from src.modules.external_data.application.dto.pdm_dto import RequestPdmFileRefreshBatchCommand
from src.modules.external_data.application.dto.pdm_dto import RequestPdmFileRefreshCommand
from src.modules.external_data.application.use_cases.pdm.get_pdm_trigger_config import (
    GetPdmTriggerConfig,
)
from src.modules.external_data.application.use_cases.pdm.request_pdm_file_refresh import (
    RequestPdmFileRefresh,
)
from src.modules.external_data.application.use_cases.pdm.validate_pdm_file import ValidatePdmFile
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_api_key_user
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.post(
    "/files/changed", status_code=status.HTTP_202_ACCEPTED, response_model=PdmFileChangedResponse
)
async def report_pdm_file_changed(
    body: PdmFileChangedRequest,
    actor: User = Depends(get_current_api_key_user),
    use_case: RequestPdmFileRefresh = Depends(get_request_pdm_file_refresh_use_case),
) -> PdmFileChangedResponse:
    """Ask Glados to refresh one PDM file. Requires use:pdm_addin.

    202: accepted, queued for the pdm_sync worker.
    400: vault_name does not match the configured vault.
    403: the API key lacks use:pdm_addin.
    409: the PDM integration is not enabled and configured.
    422: neither file_id nor path was supplied.
    429: the caller exceeded the trigger rate limit.
    """
    cmd = RequestPdmFileRefreshCommand(
        vault_name=body.vault_name, file_id=body.file_id, path=body.path, version=body.version
    )
    await use_case.execute(actor, cmd)
    return PdmFileChangedResponse(accepted=True)


@router.post(
    "/files/changed/batch",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PdmFilesChangedBatchResponse,
)
async def report_pdm_files_changed(
    body: PdmFilesChangedBatchRequest,
    actor: User = Depends(get_current_api_key_user),
    use_case: RequestPdmFileRefresh = Depends(get_request_pdm_file_refresh_use_case),
) -> PdmFilesChangedBatchResponse:
    """Ask Glados to refresh several PDM files at once (up to 100), one
    queued refresh per distinct file id. Requires use:pdm_addin. The rate
    limit counts every file.

    202: accepted, `accepted` files queued for the pdm_sync worker.
    400: vault_name does not match the configured vault.
    403: the API key lacks use:pdm_addin.
    409: the PDM integration is not enabled and configured.
    422: an empty or oversized batch, or an entry without file_id.
    429: the batch does not fit the caller's remaining trigger budget.
    """
    cmd = RequestPdmFileRefreshBatchCommand(
        vault_name=body.vault_name,
        files=[
            PdmChangedFileRef(
                file_id=f.file_id,
                path=f.path,
                version=f.version,
                reason=f.reason.value if f.reason is not None else None,
                state=f.state,
            )
            for f in body.files
        ],
    )
    accepted = await use_case.execute_batch(actor, cmd)
    return PdmFilesChangedBatchResponse(accepted=accepted)


@router.post("/files/validate/batch", response_model=PdmBatchValidationResponse)
async def validate_pdm_files(
    body: PdmBatchValidationRequest,
    actor: User = Depends(get_current_api_key_user),
    use_case: ValidatePdmFile = Depends(get_validate_pdm_file_use_case),
) -> PdmBatchValidationResponse:
    """Pre-release dry run for several vault files at once (up to 50), for
    a release of many files. Requires use:pdm_addin. Never writes
    anything. Each file gets its own outcome, so one missing or unreadable
    file never fails the call; files the time budget did not reach come
    back "not_validated".

    200: one result per distinct file id, in request order.
    403: the API key lacks use:pdm_addin.
    409: the PDM integration is not enabled and configured.
    422: an empty or oversized batch.
    """
    outcomes = await use_case.execute_batch(actor, body.file_ids)
    return PdmBatchValidationResponse(
        results=[PdmBatchValidationItem.model_validate(o.model_dump()) for o in outcomes]
    )


@router.post("/files/{file_id}/validate", response_model=PdmValidationResponse)
async def validate_pdm_file(
    file_id: int,
    actor: User = Depends(get_current_api_key_user),
    use_case: ValidatePdmFile = Depends(get_validate_pdm_file_use_case),
) -> PdmValidationResponse:
    """Pre-release dry run of the ingest rules for one vault file, resolved
    fresh from the Web API. Requires use:pdm_addin. Never writes
    anything, never fires an event.

    200: the validation result (`ok` may still be false; see `reasons`).
    403: the API key lacks use:pdm_addin.
    404: the file was not found in the vault, or is not readable for the
    PDM user (private state or missing read permission).
    409: the PDM integration is not enabled and configured.
    """
    result = await use_case.execute(actor, file_id)
    return PdmValidationResponse.model_validate(result.model_dump())


@router.get("/config", response_model=PdmTriggerConfigResponse)
async def get_pdm_trigger_config(
    actor: User = Depends(get_current_api_key_user),
    use_case: GetPdmTriggerConfig = Depends(get_pdm_trigger_config_use_case),
) -> PdmTriggerConfigResponse:
    """The add-in's own configuration read: the configured vault name and
    the release-state names driving made/bought ingest, resolved fresh
    from the vault's current workflows. Requires use:pdm_addin.

    200: vault name and release-state names.
    403: the API key lacks use:pdm_addin.
    409: the PDM integration is not enabled and configured.
    """
    result = await use_case.execute(actor)
    return PdmTriggerConfigResponse.model_validate(result.model_dump())
