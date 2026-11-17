"""
Repository interface for the PDM sync run log: PollPdmVault and
RefreshPdmFile both call `start` once, `add_entries` as they go and
`finish` once at the end; the admin sync log dialog reads back
through `get_multi`/`get_by_id`/`get_entries`, the vault add-in's file
history through `list_file_history`. `prune` is called at the end of every
run to enforce the retention policy (docs/OPERATIONS.md section 8).
ReconcilePdmVault uses this same log (trigger `reconciliation`) but writes
its findings to IPdmReconciliationFindingRepository instead of
PdmSyncRunEntry, and reads its own latest run back via `latest_by_trigger`.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRunEntry


@dataclass
class PdmSyncRunFilterDto:
    """Row filters for the runs list. Empty fields do not filter."""

    triggers: list[str] = field(default_factory=list)
    started_from: date | None = None  # inclusive calendar day
    started_to: date | None = None  # inclusive calendar day
    error: str | None = None  # substring of the run's error text


@runtime_checkable
class IPdmSyncRunRepository(Protocol):
    async def start(self, run: PdmSyncRun) -> PdmSyncRun:
        """Inserts the run row (id=0, counts still at zero, finished_at
        None) and flushes for its id. Callers commit it straight away, so a
        crash mid-run still leaves a visible, if unfinished, row for the
        admin dialog to show."""
        ...

    async def finish(self, run: PdmSyncRun) -> None:
        """Stages the run's final counts, `error` and `summary`; the caller
        commits."""
        ...

    async def save_progress(self, run: PdmSyncRun) -> None:
        """Stages the run's live progress and running counts, the same
        columns `finish` writes; the caller commits."""
        ...

    async def latest_unfinished(self, triggers: list[str]) -> PdmSyncRun | None:
        """The newest run (started_at desc) with one of `triggers` and no
        finished_at, or None. The caller decides from its progress_at
        whether it is still running or died mid-way."""
        ...

    async def recent_entries(self, limit: int) -> list[PdmSyncRunEntry]:
        """The newest `limit` entries across every run, newest first."""
        ...

    async def add_entries(self, run_id: int, entries: list[PdmSyncRunEntry]) -> None:
        """Inserts the given entries under `run_id`. Does not commit; the
        caller's own per-file transaction, or the commit that follows the
        run's `finish`, persists them."""
        ...

    async def get_multi(
        self, skip: int | None, limit: int | None, filters: PdmSyncRunFilterDto | None = None
    ) -> tuple[int, list[PdmSyncRun]]:
        """Paged, started_at desc (newest first), narrowed by `filters`
        when given."""
        ...

    async def get_by_id(self, id: int) -> PdmSyncRun | None: ...

    async def latest_by_trigger(self, trigger: str) -> PdmSyncRun | None:
        """The newest run (started_at desc) whose `trigger` matches, or
        None when no such run has ever been recorded. Used by the
        reconciliation report to find "the latest run with trigger
        reconciliation", since a report never accumulates across runs, it
        always reads the most recent one."""
        ...

    async def get_entries(
        self,
        run_id: int,
        skip: int | None,
        limit: int | None,
        action: str | None,
        search: str | None = None,
        kind: str | None = None,
    ) -> tuple[int, list[PdmSyncRunEntry]]:
        """Paged entries of one run, optionally filtered by `action`, by
        `kind`, and by `search` as a substring of the file name or path,
        oldest first (the order files were touched in)."""
        ...

    async def list_file_history(
        self, vault_id: str, file_ids: list[int], limit: int
    ) -> list[tuple[PdmSyncRunEntry, PdmSyncRun]]:
        """The newest `limit` entries of the given files in `vault_id`
        across every run, newest first, each with the run it belongs to (for
        the trigger, the requester and the reason)."""
        ...

    async def prune(self, older_than: datetime) -> int:
        """Deletes every run started before `older_than`, cascading to their
        entries. Returns the number of runs deleted."""
        ...
