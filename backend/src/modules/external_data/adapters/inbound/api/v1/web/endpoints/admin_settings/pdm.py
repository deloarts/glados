"""
Admin settings endpoints for the SolidWorks PDM tab: connection settings,
the admin API console, workflow/folder proxies, the PDM user matching
dialog, the pending-file list, the sync run log, and reconciliation
reports. All reads require read:settings; all writes require
write:settings.
"""

from datetime import date

from fastapi import Depends
from fastapi import Query
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.external_data.adapters.inbound.api.deps.settings import (
    get_browse_pdm_folders_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.settings import (
    get_dismiss_pdm_file_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.settings import (
    get_invoke_pdm_operation_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.settings import get_link_pdm_users_use_case
from src.modules.external_data.adapters.inbound.api.deps.settings import get_list_pdm_files_use_case
from src.modules.external_data.adapters.inbound.api.deps.settings import (
    get_list_pdm_operations_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.settings import (
    get_list_pdm_reconciliation_findings_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.settings import (
    get_list_pdm_sync_run_entries_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.settings import (
    get_list_pdm_sync_runs_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.settings import get_list_pdm_users_use_case
from src.modules.external_data.adapters.inbound.api.deps.settings import (
    get_pdm_reconciliation_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.settings import get_pdm_settings_use_case
from src.modules.external_data.adapters.inbound.api.deps.settings import (
    get_pdm_sync_activity_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.settings import get_pdm_workflows_use_case
from src.modules.external_data.adapters.inbound.api.deps.settings import (
    get_request_pdm_poll_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.settings import (
    get_request_pdm_reconciliation_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.settings import get_retry_pdm_file_use_case
from src.modules.external_data.adapters.inbound.api.deps.settings import (
    get_update_pdm_settings_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.settings import (
    get_verify_pdm_connection_use_case,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm import (
    AdminPdmSettingsResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm import (
    PdmConnectionTestResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm import (
    UpdatePdmSettingsRequest,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm import (
    VerifyPdmConnectionRequest,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm_vault import (
    LinkPdmUsersRequest,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm_vault import (
    PdmFileRetryResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm_vault import (
    PdmFileSnapshotResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm_vault import (
    PdmFolderResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm_vault import (
    PdmInvokeRequest,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm_vault import (
    PdmInvokeResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm_vault import (
    PdmOperationResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm_vault import (
    PdmPollResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm_vault import (
    PdmReconcileResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm_vault import (
    PdmReconciliationFindingResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm_vault import (
    PdmReconciliationReportResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm_vault import (
    PdmSyncActivityResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm_vault import (
    PdmSyncRunEntryResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm_vault import (
    PdmSyncRunResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm_vault import (
    PdmUserResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.pdm_vault import (
    PdmWorkflowResponse,
)
from src.modules.external_data.application.dto.admin_settings_dto.pdm import AdminPdmSettingsResult
from src.modules.external_data.application.dto.admin_settings_dto.pdm import PdmConnectionTestResult
from src.modules.external_data.application.dto.admin_settings_dto.pdm import (
    UpdatePdmSettingsCommand,
)
from src.modules.external_data.application.dto.admin_settings_dto.pdm import (
    VerifyPdmConnectionCommand,
)
from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import (
    InvokePdmOperationCommand,
)
from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import (
    LinkPdmUsersCommand,
)
from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import PdmFolderResult
from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import (
    PdmInvokeResultDto,
)
from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import (
    PdmOperationResult,
)
from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import PdmUserResult
from src.modules.external_data.application.dto.admin_settings_dto.pdm_vault import PdmWorkflowResult
from src.modules.external_data.application.dto.pdm_dto import PdmFileSnapshotFilterDto
from src.modules.external_data.application.dto.pdm_dto import PdmFileSnapshotResult
from src.modules.external_data.application.dto.pdm_dto import PdmReconciliationFindingFilterDto
from src.modules.external_data.application.dto.pdm_dto import PdmReconciliationFindingResult
from src.modules.external_data.application.dto.pdm_dto import PdmReconciliationReportResult
from src.modules.external_data.application.dto.pdm_dto import PdmSyncActivityResult
from src.modules.external_data.application.dto.pdm_dto import PdmSyncRunEntryResult
from src.modules.external_data.application.dto.pdm_dto import PdmSyncRunResult
from src.modules.external_data.application.use_cases.admin_settings.browse_pdm_folders import (
    BrowsePdmFolders,
)
from src.modules.external_data.application.use_cases.admin_settings.dismiss_pdm_file import (
    DismissPdmFile,
)
from src.modules.external_data.application.use_cases.admin_settings.get_pdm_reconciliation import (
    GetPdmReconciliation,
)
from src.modules.external_data.application.use_cases.admin_settings.get_pdm_settings import (
    GetPdmSettings,
)
from src.modules.external_data.application.use_cases.admin_settings.get_pdm_sync_activity import (
    GetPdmSyncActivity,
)
from src.modules.external_data.application.use_cases.admin_settings.get_pdm_workflows import (
    GetPdmWorkflows,
)
from src.modules.external_data.application.use_cases.admin_settings.invoke_pdm_operation import (
    InvokePdmOperation,
)
from src.modules.external_data.application.use_cases.admin_settings.link_pdm_users import (
    LinkPdmUsers,
)
from src.modules.external_data.application.use_cases.admin_settings.list_pdm_files import (
    ListPdmFiles,
)
from src.modules.external_data.application.use_cases.admin_settings.list_pdm_operations import (
    ListPdmOperations,
)
from src.modules.external_data.application.use_cases.admin_settings.list_pdm_reconciliation_findings import (
    ListPdmReconciliationFindings,
)
from src.modules.external_data.application.use_cases.admin_settings.list_pdm_sync_run_entries import (
    ListPdmSyncRunEntries,
)
from src.modules.external_data.application.use_cases.admin_settings.list_pdm_sync_runs import (
    ListPdmSyncRuns,
)
from src.modules.external_data.application.use_cases.admin_settings.list_pdm_users import (
    ListPdmUsers,
)
from src.modules.external_data.application.use_cases.admin_settings.request_pdm_poll import (
    RequestPdmPoll,
)
from src.modules.external_data.application.use_cases.admin_settings.request_pdm_reconciliation import (
    RequestPdmReconciliation,
)
from src.modules.external_data.application.use_cases.admin_settings.retry_pdm_file import (
    RetryPdmFile,
)
from src.modules.external_data.application.use_cases.admin_settings.update_pdm_settings import (
    UpdatePdmSettings,
)
from src.modules.external_data.application.use_cases.admin_settings.verify_pdm_connection import (
    VerifyPdmConnection,
)
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    PdmSyncRunFilterDto,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/pdm", response_model=AdminPdmSettingsResponse)
async def get_pdm_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetPdmSettings = Depends(get_pdm_settings_use_case),
) -> AdminPdmSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/pdm", response_model=AdminPdmSettingsResponse)
async def update_pdm_settings(
    body: UpdatePdmSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdatePdmSettings = Depends(get_update_pdm_settings_use_case),
) -> AdminPdmSettingsResult:
    """Configure the PDM datacard field mapping and Web API connection.
    Requires write:settings. Changing base_url, vault_name, username or
    password clears the stored session; PdmSessionService authenticates
    again on its next call. A change to the variable maps, the released/
    obsolete state lists or watched_folders requeues every skipped file
    back to pending, so a file skipped for a settings reason is picked up
    by the next poll."""
    cmd = UpdatePdmSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.post("/pdm/test", response_model=PdmConnectionTestResponse)
async def test_pdm_connection(
    body: VerifyPdmConnectionRequest,
    actor: User = Depends(get_current_active_user),
    use_case: VerifyPdmConnection = Depends(get_verify_pdm_connection_use_case),
) -> PdmConnectionTestResult:
    """Probe the SOLIDWORKS PDM Web API with the supplied (not yet saved)
    connection settings: an unauthenticated version() call followed by
    authenticate(). An empty password falls back to the one already
    stored, so the admin does not have to retype it on every test.

    200 = reached and authenticated. 400 = the connection is incomplete or
    the vault rejected the credentials. 503 = the server could not be
    reached at all. Requires write:settings. Nothing is persisted, even on
    success.
    """
    cmd = VerifyPdmConnectionCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.get("/pdm/operations", response_model=list[PdmOperationResponse])
async def list_pdm_operations(
    actor: User = Depends(get_current_active_user),
    use_case: ListPdmOperations = Depends(get_list_pdm_operations_use_case),
) -> list[PdmOperationResult]:
    """List the SOLIDWORKS PDM Web API operation catalogue for the admin API
    console. Read-only against the in-process catalogue, no call to the
    vault is made. Requires read:settings."""
    return await use_case.execute(actor=actor)


@router.post("/pdm/operations/{operation_id}/invoke", response_model=PdmInvokeResponse)
async def invoke_pdm_operation(
    operation_id: str,
    body: PdmInvokeRequest,
    actor: User = Depends(get_current_active_user),
    use_case: InvokePdmOperation = Depends(get_invoke_pdm_operation_use_case),
) -> PdmInvokeResultDto:
    """Invoke one catalogued PDM Web API operation under the saved
    connection and its shared session, for the admin API console.

    A mutating operation (checkin, delete, changestate, and the like) is
    refused with 400 unless `allow_mutating` is true on this call, the
    console's own "allow mutating operations" switch; a successful mutating
    call is recorded in the settings audit log. An unknown operation id is
    404, a missing required path parameter or a `vaultName` supplied by the
    caller (the server always fills it) is 400. Requires write:settings.
    Never logs the request or response body or the bearer token, only the
    operation id and the resulting HTTP status.
    """
    cmd = InvokePdmOperationCommand(operation_id=operation_id, **body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.get("/pdm/workflows", response_model=list[PdmWorkflowResponse])
async def get_pdm_workflows(
    actor: User = Depends(get_current_active_user),
    use_case: GetPdmWorkflows = Depends(get_pdm_workflows_use_case),
) -> list[PdmWorkflowResult]:
    """Proxy GET api/{vaultName}/workflows, for the settings page's
    released/obsolete state pickers. Requires read:settings."""
    return await use_case.execute(actor=actor)


@router.get("/pdm/folders", response_model=list[PdmFolderResponse])
async def browse_pdm_folders(
    parent_id: int = Query(default=1),
    actor: User = Depends(get_current_active_user),
    use_case: BrowsePdmFolders = Depends(get_browse_pdm_folders_use_case),
) -> list[PdmFolderResult]:
    """Proxy one level of GET api/{vaultName}/folders/{folderId}/browse,
    folders only, for the settings page's watched-folder picker.
    `parent_id` defaults to 1, the vault root. Requires read:settings."""
    return await use_case.execute(actor=actor, parent_id=parent_id)


@router.get("/pdm/users", response_model=list[PdmUserResponse])
async def list_pdm_users(
    actor: User = Depends(get_current_active_user),
    use_case: ListPdmUsers = Depends(get_list_pdm_users_use_case),
) -> list[PdmUserResult]:
    """Vault users (GET api/{vaultName}/users) cross-referenced against
    Glados users, linked via a UserPdmLink row, or a same-identity guess
    for a not-yet-linked one, for the PDM user reconciliation dialog.
    Several vault users may report the same linked or proposed Glados
    user. Requires write:settings."""
    return await use_case.execute(actor=actor)


@router.post("/pdm/users/link", status_code=status.HTTP_204_NO_CONTENT)
async def link_pdm_users(
    body: LinkPdmUsersRequest,
    actor: User = Depends(get_current_active_user),
    use_case: LinkPdmUsers = Depends(get_link_pdm_users_use_case),
) -> None:
    """Save the PDM-user-to-Glados-user links confirmed in the matching
    dialog; a null user_id unlinks. Several PDM users may link to the same
    Glados user; relinking a PDM user id already held by someone else
    moves it rather than failing. Requires write:settings."""
    cmd = LinkPdmUsersCommand(**body.model_dump())
    await use_case.execute(actor=actor, cmd=cmd)


@router.post("/pdm/poll", response_model=PdmPollResponse, status_code=status.HTTP_202_ACCEPTED)
async def request_pdm_poll(
    actor: User = Depends(get_current_active_user),
    use_case: RequestPdmPoll = Depends(get_request_pdm_poll_use_case),
) -> PdmPollResponse:
    """Queue an immediate PDM poll: clears last_poll_at so the scheduler's
    next tick (within 60 seconds) treats the vault as due, rather than
    waiting out poll_interval_minutes. 202 means queued, not done.
    409 when PDM is not enabled and configured. Requires write:settings."""
    await use_case.execute(actor=actor)
    return PdmPollResponse(accepted=True)


@router.get("/pdm/files", response_model=PageResponse[PdmFileSnapshotResponse])
async def list_pdm_files(
    skip: int | None = Query(default=None, ge=0),
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    sync_state: str | None = None,
    kind: str | None = None,
    search: str | None = None,
    actor: User = Depends(get_current_active_user),
    use_case: ListPdmFiles = Depends(get_list_pdm_files_use_case),
) -> PageResponse[PdmFileSnapshotResult]:
    """Paged, filtered list of every watched PDM file and where it stands
    in the poll -> ingest pipeline, for the admin "PDM files" pending
    list. Requires read:settings."""
    filters = PdmFileSnapshotFilterDto(
        skip=skip, limit=limit, sync_state=sync_state, kind=kind, search=search
    )
    total, files = await use_case.execute(actor=actor, filters=filters)
    return PageResponse(items=files, total=total, limit=limit, skip=skip or 0)


@router.post(
    "/pdm/files/{snapshot_id}/retry",
    response_model=PdmFileRetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_pdm_file(
    snapshot_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RetryPdmFile = Depends(get_retry_pdm_file_use_case),
) -> PdmFileRetryResponse:
    """Reset one pending-list row to pending and ask the pdm_sync worker to
    refresh it on its next tick, the same PdmFileChangeRequested path the
    poller and the vault add-in's trigger endpoint use. 202 means queued,
    not done. 404 when the snapshot id is unknown. Requires
    write:settings."""
    await use_case.execute(actor=actor, snapshot_id=snapshot_id)
    return PdmFileRetryResponse(accepted=True)


@router.post(
    "/pdm/vault-files/{file_id}/retry",
    response_model=PdmFileRetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_pdm_vault_file(
    file_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RetryPdmFile = Depends(get_retry_pdm_file_use_case),
) -> PdmFileRetryResponse:
    """The retry above, addressed by the vault file id a reconciliation
    finding carries. 404 when Glados has no snapshot of that file. Requires
    write:settings."""
    await use_case.execute_for_file(actor=actor, file_id=file_id)
    return PdmFileRetryResponse(accepted=True)


@router.post("/pdm/files/{snapshot_id}/dismiss", response_model=PdmFileSnapshotResponse)
async def dismiss_pdm_file(
    snapshot_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DismissPdmFile = Depends(get_dismiss_pdm_file_use_case),
) -> PdmFileSnapshotResult:
    """Dismiss one pending-list row without contacting PDM: marks it
    skipped and drops any parked ingest payload. 404 when the snapshot id
    is unknown. Requires write:settings."""
    return await use_case.execute(actor=actor, snapshot_id=snapshot_id)


@router.get("/pdm/sync-activity", response_model=PdmSyncActivityResponse)
async def get_pdm_sync_activity(
    actor: User = Depends(get_current_active_user),
    use_case: GetPdmSyncActivity = Depends(get_pdm_sync_activity_use_case),
) -> PdmSyncActivityResult:
    """What the PDM sync is doing right now, for the "Synchronize with PDM"
    button and its activity dialog: whether a synchronisation is requested
    and waiting for the scheduler, the poll run in progress with its live
    progress, and the newest processed files across every run. Cheap enough
    to poll every few seconds. Requires read:settings."""
    return await use_case.execute(actor=actor)


@router.get("/pdm/runs", response_model=PageResponse[PdmSyncRunResponse])
async def list_pdm_sync_runs(
    skip: int | None = Query(default=None, ge=0),
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    trigger: list[str] | None = Query(default=None),
    started_from: date | None = None,
    started_to: date | None = None,
    error: str | None = None,
    actor: User = Depends(get_current_active_user),
    use_case: ListPdmSyncRuns = Depends(get_list_pdm_sync_runs_use_case),
) -> PageResponse[PdmSyncRunResult]:
    """Paged, newest-first list of the PDM sync run log (poll ticks and
    single-file refreshes) for the admin sync log dialog. `trigger`
    may repeat to match any of several triggers, `started_from`/`started_to`
    are inclusive calendar days and `error` matches a substring of the run's
    error text. Requires read:settings."""
    filters = PdmSyncRunFilterDto(
        triggers=trigger or [],
        started_from=started_from,
        started_to=started_to,
        error=error,
    )
    total, runs = await use_case.execute(actor=actor, skip=skip, limit=limit, filters=filters)
    return PageResponse(items=runs, total=total, limit=limit, skip=skip or 0)


@router.get("/pdm/runs/{run_id}/entries", response_model=PageResponse[PdmSyncRunEntryResponse])
async def list_pdm_sync_run_entries(
    run_id: int,
    skip: int | None = Query(default=None, ge=0),
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    action: str | None = None,
    kind: str | None = None,
    search: str | None = None,
    actor: User = Depends(get_current_active_user),
    use_case: ListPdmSyncRunEntries = Depends(get_list_pdm_sync_run_entries_use_case),
) -> PageResponse[PdmSyncRunEntryResult]:
    """Paged list of one sync run's per-file entries, shown on selecting a
    row in the sync log dialog's runs list, optionally filtered by
    action, by kind, and by `search` as a substring of the file name or
    path. 404 when the run id is unknown. Requires read:settings."""
    total, entries = await use_case.execute(
        actor=actor,
        run_id=run_id,
        skip=skip,
        limit=limit,
        action=action,
        search=search,
        kind=kind,
    )
    return PageResponse(items=entries, total=total, limit=limit, skip=skip or 0)


@router.post(
    "/pdm/reconcile", response_model=PdmReconcileResponse, status_code=status.HTTP_202_ACCEPTED
)
async def request_pdm_reconciliation(
    deep: bool = Query(default=False),
    actor: User = Depends(get_current_active_user),
    use_case: RequestPdmReconciliation = Depends(get_request_pdm_reconciliation_use_case),
) -> PdmReconcileResponse:
    """Queue a reconciliation report (`deep=false` reads only the
    database, `deep=true` additionally checks every linked file's
    write-back datacard variables): the scheduler's next tick (within 60
    seconds) runs it before its own poll-interval check. 202 means queued,
    not done. 409 when PDM is not enabled and configured. Requires
    write:settings."""
    await use_case.execute(actor=actor, deep=deep)
    return PdmReconcileResponse(accepted=True)


@router.get("/pdm/reconciliation", response_model=PdmReconciliationReportResponse)
async def get_pdm_reconciliation(
    actor: User = Depends(get_current_active_user),
    use_case: GetPdmReconciliation = Depends(get_pdm_reconciliation_use_case),
) -> PdmReconciliationReportResult:
    """The latest reconciliation report: the run it came from (null when
    reconciliation has never run) plus how many files each category's
    findings stand for. Requires read:settings."""
    return await use_case.execute(actor=actor)


@router.get(
    "/pdm/reconciliation/findings", response_model=PageResponse[PdmReconciliationFindingResponse]
)
async def list_pdm_reconciliation_findings(
    skip: int | None = Query(default=None, ge=0),
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    category: str | None = None,
    kind: str | None = None,
    search: str | None = None,
    part_number: str | None = None,
    message: str | None = None,
    actor: User = Depends(get_current_active_user),
    use_case: ListPdmReconciliationFindings = Depends(
        get_list_pdm_reconciliation_findings_use_case
    ),
) -> PageResponse[PdmReconciliationFindingResult]:
    """Paged, filtered findings of the latest reconciliation report.
    `search` matches the part number or the message, `part_number` and
    `message` each match only their own column. Requires read:settings."""
    filters = PdmReconciliationFindingFilterDto(
        skip=skip,
        limit=limit,
        category=category,
        kind=kind,
        search=search,
        part_number=part_number,
        message=message,
    )
    total, findings = await use_case.execute(actor=actor, filters=filters)
    return PageResponse(items=findings, total=total, limit=limit, skip=skip or 0)
