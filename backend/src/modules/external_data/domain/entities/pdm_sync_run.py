"""
One row per PDM sync attempt (a poller tick or a single-file refresh),
plus the per-file entries it produced, the audit trail behind the poller's
own last_poll_at/last_poll_error/last_poll_summary status line (those three
columns only ever hold the latest run; this table keeps history). A
PollPdmVault run writes one PdmSyncRun with one PdmSyncRunEntry per touched
file (changed, missing, conflict retry); a RefreshPdmFile call writes a
one-entry run for the single file it was asked to refresh. See
PdmSyncTrigger for what `trigger` can hold and docs/OPERATIONS.md section 8 for
the retention policy (runs older than SYNC_RUN_RETENTION, pruned at the end
of every run). Age rather than a run count, because every single-file
refresh is a run of its own, so a count would let a busy vault push a
file's history out within hours.
"""

from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta

from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.shared_kernel.domain.entities.base import Entity

SYNC_RUN_RETENTION = timedelta(days=30)


@dataclass
class PdmSyncRun(Entity):
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
    error: str | None  # a top-level failure that aborted the run, if any
    summary: str | None  # human-readable one-liner, mirrors last_poll_summary
    # Folders successfully browsed this run (the recursive walk's own cost
    # measure): a single-file refresh never browses a folder, so this stays
    # 0 on that kind of run.
    folders_walked: int
    # Cold-folder poll cadence (domain.services.pdm_poll_cadence): folders
    # a scheduled run skipped entirely because their own next_due_at was
    # still in the future. Always 0 on a manual/initial run (both walk
    # every folder regardless) and on a single-file refresh.
    folders_skipped_cold: int = 0
    # Live progress of a running poll, written while it runs and read by the
    # admin sync activity dialog: the current phase ("walking", "ingesting"),
    # the watched folder being walked, how many changed files were queued and
    # processed so far, and when this was last written. A run whose progress
    # stops being written while it is still unfinished died mid-way.
    phase: str | None = None
    current_path: str | None = None
    files_queued: int = 0
    files_processed: int = 0
    progress_at: datetime | None = None
    # Who asked for a single-file refresh and why, as the request said:
    # the requester's full name at the time, the caller's PdmChangeReason
    # value and, for a state change, the destination state name. None on
    # every poll and reconciliation run, and on a trigger that gave none.
    change_reason: str | None = None
    change_state: str | None = None
    requested_by_name: str | None = None


@dataclass
class PdmSyncRunEntry(Entity):
    run_id: int
    vault_id: str
    file_id: int
    name: str
    path: str
    kind: str | None  # "made" | "bought" | None when the file matched no watched folder
    action: str  # IngestOutcome.action, plus "missing" and "error"
    item_id: int | None
    message: str
    created_at: datetime
