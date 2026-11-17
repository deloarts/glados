"""
PAT surface, pre-release validation: the SolidWorks add-in's validate
button posts the document's
own custom-property values here after saving its Glados.* properties, and
shows the verdict next to its sync indicator without ever blocking a
save. Standard PAT auth, no extra permission: same posture as the other
read-only PAT endpoints (settings.py's field-mapping), since this neither
writes anything nor reads anything sensitive beyond the caller's own
values. Unlike the API-key surface's POST {API_KEY}/pdm/files/{file_id}/
validate, the add-in has no vault-issued file id of its own, only
optionally the document's local path (`file_path`), which
ValidatePdmPayload resolves against the snapshot table itself (see its
own module docstring and ValidatePdmPayloadCommand's). The response's
`file_identity` tells the caller whether that resolution succeeded.

Also the change-notification trigger in its batch form, the same contract
as POST {API_KEY}/pdm/files/changed/batch but signed in with the caller's
own PAT, which is how the vault add-in reaches Glados: each Windows user
signs in on the add-in's vault view tab, so the trigger is attributed to
that user and rate limited per user. It needs use:pdm_addin, the one
permission of the PDM add-in token preset (PDM_ADDIN_SCOPES).

And the file history read, under the same permission: the add-in shows
what Glados did with the files a user selects in the vault view. See
ListPdmFileHistory.
"""

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.external_data.adapters.inbound.api.deps.pdm import (
    get_list_pdm_file_history_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.pdm import (
    get_request_pdm_file_refresh_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.pdm import (
    get_validate_pdm_payload_use_case,
)
from src.modules.external_data.adapters.inbound.api.schemas.pdm_schema import PdmFileHistoryRequest
from src.modules.external_data.adapters.inbound.api.schemas.pdm_schema import PdmFileHistoryResponse
from src.modules.external_data.adapters.inbound.api.schemas.pdm_schema import (
    PdmFilesChangedBatchRequest,
)
from src.modules.external_data.adapters.inbound.api.schemas.pdm_schema import (
    PdmFilesChangedBatchResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.pdm_schema import (
    PdmValidatePayloadRequest,
)
from src.modules.external_data.adapters.inbound.api.schemas.pdm_schema import PdmValidationResponse
from src.modules.external_data.application.dto.pdm_dto import ListPdmFileHistoryCommand
from src.modules.external_data.application.dto.pdm_dto import PdmChangedFileRef
from src.modules.external_data.application.dto.pdm_dto import RequestPdmFileRefreshBatchCommand
from src.modules.external_data.application.dto.pdm_dto import ValidatePdmPayloadCommand
from src.modules.external_data.application.use_cases.pdm.list_pdm_file_history import (
    ListPdmFileHistory,
)
from src.modules.external_data.application.use_cases.pdm.request_pdm_file_refresh import (
    RequestPdmFileRefresh,
)
from src.modules.external_data.application.use_cases.pdm.validate_pdm_payload import (
    ValidatePdmPayload,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.post("/validate", response_model=PdmValidationResponse)
async def validate_pdm_payload(
    body: PdmValidatePayloadRequest,
    _: User = Depends(get_current_user_pat),
    use_case: ValidatePdmPayload = Depends(get_validate_pdm_payload_use_case),
) -> PdmValidationResponse:
    """Pre-release dry run of the ingest rules against a raw property bag
    the caller already has in hand (no vault round trip). Never writes
    anything, never fires an event.

    200: the validation result (`ok` may still be false; see `reasons`).
    409: the PDM integration is not enabled and configured.
    """
    cmd = ValidatePdmPayloadCommand(
        kind=body.kind,
        variables=body.variables,
        file_name=body.file_name,
        file_path=body.file_path,
    )
    result = await use_case.execute(cmd)
    return PdmValidationResponse.model_validate(result.model_dump())


@router.post(
    "/files/changed/batch",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PdmFilesChangedBatchResponse,
)
async def report_pdm_files_changed(
    body: PdmFilesChangedBatchRequest,
    actor: User = Depends(get_current_user_pat),
    use_case: RequestPdmFileRefresh = Depends(get_request_pdm_file_refresh_use_case),
) -> PdmFilesChangedBatchResponse:
    """Ask Glados to refresh several PDM files at once (up to 100), one
    queued refresh per distinct file id. Requires use:pdm_addin on the
    token. The rate limit counts every file and is kept per user.

    202: accepted, `accepted` files queued for the pdm_sync worker.
    400: vault_name does not match the configured vault.
    403: the token lacks use:pdm_addin.
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


@router.post("/files/history", response_model=PdmFileHistoryResponse)
async def list_pdm_file_history(
    body: PdmFileHistoryRequest,
    actor: User = Depends(get_current_user_pat),
    use_case: ListPdmFileHistory = Depends(get_list_pdm_file_history_use_case),
) -> PdmFileHistoryResponse:
    """The sync log entries of up to 100 files, merged and newest first, at
    most `limit` of them. Requires use:pdm_addin on the token. Never writes
    anything. A file the worker has not processed yet has no entry.

    200: the entries, possibly none.
    400: vault_name does not match the configured vault.
    403: the token lacks use:pdm_addin.
    409: the PDM integration is not enabled and configured.
    422: an empty or oversized file list, or a limit out of range.
    """
    cmd = ListPdmFileHistoryCommand(
        vault_name=body.vault_name, file_ids=body.file_ids, limit=body.limit
    )
    entries = await use_case.execute(actor, cmd)
    return PdmFileHistoryResponse.model_validate(
        {"entries": [entry.model_dump() for entry in entries]}
    )
