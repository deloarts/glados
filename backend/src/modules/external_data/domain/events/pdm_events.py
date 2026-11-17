"""
Domain events for PDM ingest (docs/FIELD_OWNERSHIP.md, IngestPdmFile):
PdmFileIngested on every successful write (created/revised/updated/status/
claimed), PdmIngestConflict when a write is parked instead (§7). Both
identify the file by (vault_id, file_id), the same address the PDM Web API
uses, rather than only the Glados item id, so a consumer (notifications,
the admin pending list) can link back to the file even when ingest never
resolved an item. PdmFileChangeRequested is the inbound trigger: a vault
add-in, the admin retry action or a Dispatch script says "this file
changed" and the pdm_sync worker fetches the file and runs ingest.

`source` on PdmFileChangeRequested records which of the two publishers
raised it: RequestPdmFileRefresh (the add-in/API-key trigger endpoint)
sends "file_trigger", RetryPdmFile (the admin pending list's Retry action)
sends "retry", so _handle_pdm_sync_event can tell RefreshPdmFile which
PdmSyncTrigger to record its one-entry run under.

`reason` and `state` are the caller's own account of what happened in the
vault (a PdmChangeReason value, and the destination state name of a state
change), and `requested_by_name` is the requester's full name at the time
of the request. RefreshPdmFile records all three on its run so the file
history can show them. `reason` and `state` default to None because the
retry action has no account of a vault change to give.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class PdmFileIngested(DomainEvent):
    vault_id: str
    file_id: int
    kind: str  # "made" | "bought"
    item_id: int
    action: str  # "created" | "revised" | "updated" | "status" | "claimed"
    part_number: str | None
    revision: str | None


@dataclass(frozen=True)
class PdmIngestConflict(DomainEvent):
    vault_id: str
    file_id: int
    kind: str  # "made" | "bought"
    part_number: str | None
    reason: str


@dataclass(frozen=True)
class PdmFileChangeRequested(DomainEvent):
    """Ask the sync worker to refresh one file. Either file_id or path is
    set; version is a hint only, the worker re-reads it from PDM."""

    vault_name: str
    file_id: int | None
    path: str | None
    version: int | None
    requested_by_id: int | None
    source: str  # "file_trigger" | "retry", see module docstring
    requested_by_name: str
    reason: str | None = None  # PdmChangeReason value, see module docstring
    state: str | None = None
