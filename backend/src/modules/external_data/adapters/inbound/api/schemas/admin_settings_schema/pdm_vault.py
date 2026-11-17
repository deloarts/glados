"""
HTTP request and response schemas for the PDM vault access from the admin
settings page: the Web API console, workflows, folders, user linking, polling,
file snapshots, sync runs and reconciliation.
"""

from datetime import datetime

from pydantic import BaseModel

from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_reconciliation_category import (
    PdmReconciliationCategory,
)
from src.modules.external_data.domain.value_objects.pdm_reconciliation_severity import (
    PdmReconciliationSeverity,
)
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class PdmInvokeRequest(BaseModel):
    path_params: dict[str, object] = {}
    query: dict[str, object] = {}
    body: object | None = None
    allow_mutating: bool = False


class PdmWorkflowStateResponse(ResponseModel):
    state_id: int
    state_name: str


class PdmWorkflowResponse(ResponseModel):
    workflow_id: int
    workflow_name: str
    states: list[PdmWorkflowStateResponse]


class PdmFolderResponse(ResponseModel):
    id: int
    name: str
    path: str


class PdmUserResponse(ResponseModel):
    """One vault user for the Match PDM Users dialog. `is_service_account`
    marks the login the connection itself uses; that user is never proposed
    or linkable."""

    pdm_user_id: int
    username: str
    full_name: str
    is_service_account: bool
    linked_user_id: int | None
    proposed_user_id: int | None


class LinkPdmUserEntryRequest(BaseModel):
    pdm_user_id: int
    user_id: int | None = None  # None unlinks


class LinkPdmUsersRequest(BaseModel):
    links: list[LinkPdmUserEntryRequest]


class PdmPollResponse(ResponseModel):
    accepted: bool


class PdmParamResponse(ResponseModel):
    name: str
    location: str
    type: str
    required: bool
    description: str


class PdmOperationResponse(ResponseModel):
    id: str
    method: str
    path: str
    group: str
    description: str
    params: list[PdmParamResponse]
    has_body: bool
    body_example: str | None
    mutating: bool


class PdmInvokeResponse(ResponseModel):
    method: str
    url: str
    status_code: int
    elapsed_ms: int
    content_type: str
    response_json: object | None
    response_text: str | None


# Mirrors PdmFileSnapshotResult, except that the parked payload stays
# server-side and only `has_parked_payload` is sent.
class PdmFileSnapshotResponse(EntityResponse):
    """One file the poller knows from the vault."""

    vault_id: str
    file_id: int
    kind: str | None
    name: str
    path: str
    parent_folder_id: int
    version: int
    state_id: int
    state: str
    modified_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    last_ingested_version: int | None
    sync_state: PdmFileSyncState
    last_error: str | None
    part_number: str | None
    revision: str | None
    item_id: int | None
    # "made" or "bought": the catalogue item_id belongs to, also for a
    # document row, whose own kind is "document".
    item_kind: str | None
    has_parked_payload: bool


class PdmFileRetryResponse(ResponseModel):
    accepted: bool


class PdmSyncRunResponse(EntityResponse):
    """One sync run of the sync log."""

    started_at: datetime
    finished_at: datetime | None
    trigger: PdmSyncTrigger
    files_seen: int
    changed: int
    ingested: int
    skipped: int
    conflicts: int
    errors: int
    missing: int
    error: str | None
    summary: str | None
    folders_walked: int
    folders_skipped_cold: int
    # Live progress while the run is unfinished: "walking", "ingesting" or
    # "finishing", the folder being walked, changed files queued and
    # processed so far, and when this was last written.
    phase: str | None
    current_path: str | None
    files_queued: int
    files_processed: int
    progress_at: datetime | None


class PdmSyncRunEntryResponse(EntityResponse):
    """One file a sync run touched."""

    run_id: int
    vault_id: str
    file_id: int
    name: str
    path: str
    kind: str | None
    action: str
    item_id: int | None
    message: str
    created_at: datetime


class PdmSyncActivityResponse(ResponseModel):
    """What the PDM sync is doing now: whether a sync was requested and waits
    for the scheduler, the run in progress if any, and the newest processed
    files across every run."""

    requested: bool
    run: PdmSyncRunResponse | None
    recent_entries: list[PdmSyncRunEntryResponse]


class PdmReconcileResponse(ResponseModel):
    accepted: bool


class PdmReconciliationFindingResponse(EntityResponse):
    """One finding of a reconciliation run."""

    run_id: int
    category: PdmReconciliationCategory
    severity: PdmReconciliationSeverity
    kind: str | None
    item_id: int | None
    file_id: int | None
    part_number: str | None
    revision: str | None
    message: str
    count: int
    created_at: datetime


class PdmReconciliationReportResponse(ResponseModel):
    run: PdmSyncRunResponse | None
    counts: dict[str, int]
