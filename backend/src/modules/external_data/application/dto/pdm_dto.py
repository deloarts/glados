"""
DTOs for the PDM file snapshot list, PDM ingest, the sync log, the
reconciliation report and payload validation.

The filter DTOs mirror the same-named dataclasses in the repository ports and
are kept in sync by field list, because ports may not import application.
PdmFilePayload is one file's already-resolved ingest input, so IngestPdmFile
never talks to the gateway itself. ValidatePdmPayloadCommand identifies the
file either by vault_id and file_id (API-key surface) or by file_path (PAT
surface), and PdmValidationResult.file_identity reports whether that worked."""

from datetime import datetime

from pydantic import BaseModel

from src.modules.platform.application.dto.base import ResultBase


class PdmFileSnapshotFilterDto(BaseModel):
    skip: int | None = None
    limit: int | None = None
    sync_state: str | None = None
    kind: str | None = None
    search: str | None = None  # matches name, path, part_number


class PdmFileSnapshotResult(ResultBase):
    """One row of the admin "PDM files" pending list. Mirrors PdmFileSnapshot
    field for field except `parked_payload`, which can hold arbitrary datacard
    values from a conflicted ingest and never leaves the API; it is reduced to
    `has_parked_payload`, which enables the retry button."""

    vault_id: str
    file_id: int
    kind: str | None  # "made" | "bought" | None (unresolved, by_kind folder)
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
    sync_state: str
    last_error: str | None
    part_number: str | None
    revision: str | None
    item_id: int | None
    # The catalogue `item_id` belongs to, "made" or "bought". A document
    # row's own kind is "document", so this is the only way to tell.
    item_kind: str | None
    has_parked_payload: bool


class PdmFilePayload(BaseModel):
    vault_id: str
    file_id: int
    file_version: int
    path: str
    name: str
    parent_folder_id: int
    state_id: int
    state: str
    kind: str  # "made" | "bought"
    variables: dict[str, str]  # the selected configuration's raw datacard values
    modified_at: datetime | None = None


class IngestOutcome(BaseModel):
    # "created" | "revised" | "updated" | "status" | "claimed" | "skipped" | "conflict"
    action: str
    item_id: int | None
    message: str


class RequestPdmFileRefreshCommand(BaseModel):
    """Input to RequestPdmFileRefresh, the API-key trigger endpoint's use
    case: `vault_name` must equal the configured vault (case-insensitive),
    and either `file_id` or `path` must be set, enforced by
    PdmFileChangedRequest's own validator, not repeated here, so an
    already-invalid command never reaches the use case."""

    vault_name: str
    file_id: int | None = None
    path: str | None = None
    version: int | None = None


class PdmChangedFileRef(BaseModel):
    """One file of a batch trigger: the vault-issued file id plus the same
    optional path and version hints the single-file trigger carries, and the
    caller's reason (a PdmChangeReason value) and destination state name,
    which only label the file's history."""

    file_id: int
    path: str | None = None
    version: int | None = None
    reason: str | None = None
    state: str | None = None


class RequestPdmFileRefreshBatchCommand(BaseModel):
    """Input to RequestPdmFileRefresh.execute_batch: several changed files
    of one vault in a single call, so a batch operation in PDM (a folder
    moved, many files released) costs one round trip instead of one per
    file."""

    vault_name: str
    files: list[PdmChangedFileRef]


class ListPdmFileHistoryCommand(BaseModel):
    """Input to ListPdmFileHistory: the files' vault, their vault-issued ids
    and how many entries to return at most across all of them."""

    vault_name: str
    file_ids: list[int]
    limit: int


class PdmFileHistoryEntryResult(BaseModel):
    """One sync log entry of a requested file with the run it belongs to.
    `trigger` is the run's PdmSyncTrigger value; `change_reason`,
    `change_state` and `requested_by_name` are set only on a single-file
    refresh whose request carried them. No item id or part data on purpose:
    the history says what Glados did with the file, not what the file
    produced."""

    file_id: int
    name: str
    path: str
    kind: str | None
    action: str
    message: str
    created_at: datetime
    run_id: int
    trigger: str
    run_started_at: datetime
    run_finished_at: datetime | None
    run_error: str | None
    change_reason: str | None
    change_state: str | None
    requested_by_name: str | None


class PdmTriggerConfigResult(BaseModel):
    """Result of GetPdmTriggerConfig (GET {API_KEY}/pdm/config): gives an
    API-key caller the release-state names it should treat as "released"
    without hardcoding them. `release_state_names` is the
    union of every id in `made_released_state_ids` and
    `bought_released_state_ids` resolved to its workflow state name
    through IPdmGateway.workflows(), deduplicated and sorted; an id no
    workflow currently knows is silently dropped."""

    vault_name: str
    release_state_names: list[str]


# ── Sync run log ────────────────────────────────────────────────────────


class PdmSyncRunResult(ResultBase):
    """One row of the admin sync log runs list."""

    started_at: datetime
    finished_at: datetime | None
    trigger: str  # PdmSyncTrigger
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
    phase: str | None = None
    current_path: str | None = None
    files_queued: int = 0
    files_processed: int = 0
    progress_at: datetime | None = None


class ValidatePdmPayloadCommand(BaseModel):
    kind: str | None  # "made" | "bought" | None (resolve from variables' kind variable)
    variables: dict[str, str]
    file_name: str | None = None
    vault_id: str | None = None
    file_id: int | None = None
    # PAT surface only: the document's full local path (e.g.
    # "C:\DEMO-VAULT\Engineering\Glados\CAD-1001.sldprt"), used to
    # resolve vault_id/file_id via the snapshot table when the caller has
    # not already supplied them directly, see PdmValidationResult.
    # file_identity's docstring below.
    file_path: str | None = None


class PdmValidationResult(BaseModel):
    ok: bool
    reasons: list[str]
    # Fields missing that are PDM-owned (item_field_ownership.item_fields'
    # owner "pdm", e.g. part_number, revision): never a `reasons` entry and
    # never fails `ok`, since the PDM release workflow assigns them, not
    # the engineer looking at this result before release. Bare field
    # names, in item_fields() order; see validate_pdm_payload.py's module
    # docstring for the pre-release semantics this backs.
    pending_pdm: list[str] = []
    kind: str | None
    part_number: str | None
    revision: str | None
    # "created" | "revised" | "updated" | "claimed" | "status" | "unknown".
    # "status" is kept for shape parity with IngestOutcome.action but is
    # never produced here; validation always simulates a released
    # (active) target, see validate_pdm_payload.py's module docstring.
    # Predicted as if every `pending_pdm` field had already been assigned:
    # no part number is "created", a known part number with the family's
    # revision still pending is "revised" (made) or the normal bought
    # claim/create/update outcome (bought, whose identity is the part
    # number alone).
    would: str
    # "resolved" (file_path matched exactly one snapshot row), "unresolved"
    # (no file_path, or none/more than one snapshot matched) or
    # "not_applicable" (the API-key surface already hands vault_id/file_id
    # directly, no path resolution ever happens there). Unresolved never
    # fails validation on its own: a row already linked to a PDM file
    # simply comes back as "updated" rather than a guessed "linked to
    # another PDM file", see validate_pdm_payload.py's _would_bought.
    file_identity: str
    # Advisory, verdict-irrelevant context for the caller to display
    # alongside `reasons`; it currently only ever carries the
    # file-identity-unresolved-with-a-linked-row note.
    notes: list[str] = []


class PdmBatchValidationOutcome(BaseModel):
    """One file's answer in ValidatePdmFile.execute_batch. `outcome` is
    "validated" (`validation` holds the dry run), "not_found" (the file does
    not resolve or is not readable for the PDM user, the single-file
    endpoint's 404), "failed" (a PDM Web API error while reading it) or
    "not_validated" (the batch ran out of time before reaching it). Only a
    validated result with `ok` false is meant to stop a release."""

    file_id: int
    outcome: str
    detail: str | None = None
    validation: PdmValidationResult | None = None


class PdmSyncRunEntryResult(ResultBase):
    """One row of a sync run's entries list."""

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


# ── Reconciliation report ────────────────────────────────────────────────


class PdmSyncActivityResult(BaseModel):
    """What the PDM sync is doing right now, for the admin activity dialog:
    whether a synchronisation was requested and is waiting for the
    scheduler, the poll run in progress if any, and the newest processed
    files across every run."""

    requested: bool
    run: PdmSyncRunResult | None
    recent_entries: list[PdmSyncRunEntryResult]


class PdmReconciliationFindingFilterDto(BaseModel):
    """Pydantic mirror of IPdmReconciliationFindingRepository's same-named
    port dataclass, for the API/use-case boundary; see
    PdmFileSnapshotFilterDto's docstring above for why the two are kept
    separate rather than shared."""

    skip: int | None = None
    limit: int | None = None
    category: str | None = None
    kind: str | None = None
    search: str | None = None  # matches part_number, message
    part_number: str | None = None  # substring of part_number only
    message: str | None = None  # substring of message only


class PdmReconciliationFindingResult(ResultBase):
    """One row of the admin reconciliation dialog's findings list. Mirrors
    PdmReconciliationFinding field for field."""

    run_id: int
    category: str  # PdmReconciliationCategory
    severity: str  # PdmReconciliationSeverity
    kind: str | None
    item_id: int | None
    file_id: int | None
    part_number: str | None
    revision: str | None
    message: str
    count: int
    created_at: datetime


class PdmReconciliationReportResult(BaseModel):
    """GET /admin/settings/pdm/reconciliation: the latest reconciliation
    run (None when reconciliation has never run) plus how many files each
    category's findings stand for (counts_for_run sums `count`, not row
    count, so an aggregated `stuck_file`/`document_unmatched` row is
    weighted by the files it represents)."""

    run: PdmSyncRunResult | None
    counts: dict[str, int]
