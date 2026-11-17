"""
Wire schema for the API-key surface's PDM change-notification trigger
(POST {API_KEY}/pdm/files/changed and its /batch form), pre-release
validation (POST {API_KEY}/pdm/files/{file_id}/validate and POST
{API_KEY}/pdm/files/validate/batch) and trigger config read (GET
{API_KEY}/pdm/config), plus the PAT surface's own validation request
(POST /api/v1/pat/pdm/validate), its trigger batch, which reuses the
API-key surface's batch schemas (POST /api/v1/pat/pdm/files/changed/batch),
and its file history read (POST /api/v1/pat/pdm/files/history).
This is a separate module from the admin_settings_schema package's own
Pdm* schemas on purpose: these are the key and PAT surfaces the vault
add-in, the SolidWorks add-in and scripted callers use, not part of the
admin settings surface those belong to.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator

from src.modules.external_data.domain.value_objects.pdm_change_reason import PdmChangeReason
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class PdmFileChangedRequest(BaseModel):
    vault_name: str
    file_id: int | None = None
    path: str | None = None
    version: int | None = None

    @model_validator(mode="after")
    def require_file_id_or_path(self) -> "PdmFileChangedRequest":
        if self.file_id is None and self.path is None:
            raise ValueError("Either file_id or path must be provided.")
        return self


class PdmFileChangedResponse(ResponseModel):
    accepted: bool


# Upper bounds per batch call, so one request stays small and quick to
# answer; a caller such as the vault add-in splits larger operations into
# several calls.
MAX_TRIGGER_BATCH = 100
MAX_VALIDATION_BATCH = 50


# Longest destination state name a trigger may carry; PDM's own state names
# are far shorter, this only keeps a misbehaving caller's label bounded.
MAX_STATE_NAME_LENGTH = 200


class PdmChangedFile(BaseModel):
    """`reason` and `state` say what happened in the vault, for the file
    history only; Glados refreshes the file the same way without them."""

    file_id: int
    path: str | None = None
    version: int | None = None
    reason: PdmChangeReason | None = None
    state: str | None = Field(default=None, max_length=MAX_STATE_NAME_LENGTH)


class PdmFilesChangedBatchRequest(BaseModel):
    """Several changed files of one vault. Unlike the single-file trigger,
    every entry needs its vault-issued file id, since the add-in always has
    it."""

    vault_name: str
    files: list[PdmChangedFile] = Field(min_length=1, max_length=MAX_TRIGGER_BATCH)


class PdmFilesChangedBatchResponse(ResponseModel):
    """`accepted` is the number of distinct files queued for a refresh."""

    accepted: int


# Mirrors application.dto.pdm_dto.PdmTriggerConfigResult field for field.
class PdmTriggerConfigResponse(ResponseModel):
    """The vault name and the release-state names, so a caller that checks
    releases itself reads them from Glados instead of hardcoding them."""

    vault_name: str
    release_state_names: list[str]


# Mirrors application.dto.pdm_dto.PdmValidationResult field for field.
class PdmValidationResponse(ResponseModel):
    """The verdict of both pre-release validation endpoints. `ok` is false
    exactly when `reasons` is not empty. `file_identity` is "resolved" or
    "unresolved" on the PAT surface, depending on whether `file_path`
    matched a known PDM file, and "not_applicable" on the API-key surface,
    which already sends a file id. `notes` is advisory context and
    `pending_pdm` names the PDM-owned required fields still missing
    (typically `part_number` and `revision` before a release); neither
    affects `ok`, since the release workflow assigns those fields."""

    ok: bool
    reasons: list[str]
    pending_pdm: list[str] = Field(default=[])
    kind: str | None
    part_number: str | None
    revision: str | None
    would: str
    file_identity: str
    notes: list[str] = Field(default=[])


class PdmBatchValidationRequest(BaseModel):
    file_ids: list[int] = Field(min_length=1, max_length=MAX_VALIDATION_BATCH)


# Mirrors application.dto.pdm_dto.PdmBatchValidationOutcome.
class PdmBatchValidationItem(ResponseModel):
    """One file's answer. `outcome` is "validated" (`validation` is set),
    "not_found", "failed" or "not_validated" (the time budget ran out).
    Only a validated result with `ok` false is meant to stop a release."""

    file_id: int
    outcome: Literal["validated", "not_found", "failed", "not_validated"]
    detail: str | None = None
    validation: PdmValidationResponse | None = None


class PdmBatchValidationResponse(ResponseModel):
    results: list[PdmBatchValidationItem]


class PdmValidatePayloadRequest(BaseModel):
    """The SolidWorks add-in's read of the document's custom properties,
    keyed by the variable names of the configured field mapping, the same
    mapping a real ingest uses. `kind` is the catalogue the add-in saved
    from, or null to read it from `variables` as a "by datacard" watched
    folder would. `file_path` is the document's full local path (for
    example "C:\\DEMO-VAULT\\Engineering\\Glados\\CAD-1001.sldprt"). It is
    optional, but only with it can the file be matched to a PDM file and
    get the same file-identity checks the API-key surface runs."""

    kind: Literal["made", "bought"] | None = None
    file_name: str | None = None
    file_path: str | None = None
    variables: dict[str, str]


# The history read takes as many files as one trigger batch, so a selection
# the add-in can trigger it can also look up in one call.
MAX_HISTORY_FILES = MAX_TRIGGER_BATCH
MAX_HISTORY_ENTRIES = 200


class PdmFileHistoryRequest(BaseModel):
    """The files whose sync history to read, by vault-issued id, and the
    most entries to return across all of them."""

    vault_name: str
    file_ids: list[int] = Field(min_length=1, max_length=MAX_HISTORY_FILES)
    limit: int = Field(default=50, ge=1, le=MAX_HISTORY_ENTRIES)


# Mirrors application.dto.pdm_dto.PdmFileHistoryEntryResult field for field.
class PdmFileHistoryEntry(ResponseModel):
    """One sync log entry of a requested file. `action` is what Glados did
    with it (created, revised, updated, status, claimed, skipped, conflict,
    missing, error, or a document or write-back action) and `message` says
    why. `trigger` is what started the run (file_trigger, retry, scheduled,
    manual, initial). `change_reason` (state_change, check_in, delete,
    move, rename, resync, add, copy), `change_state` and
    `requested_by_name` are set only on a single-file refresh whose request
    carried them."""

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


class PdmFileHistoryResponse(ResponseModel):
    """The requested files' entries merged, newest first."""

    entries: list[PdmFileHistoryEntry]
