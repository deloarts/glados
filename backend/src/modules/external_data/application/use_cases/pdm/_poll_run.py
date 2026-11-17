"""The run bookkeeping of the PDM poll: the in-memory tally of one run
(PollSummary), its live progress on the run row, the closing of the run and
the one-line summary the admin UI shows. The behaviour is documented in
docs/reference/pdm-sync.md section 3.11.

PollRunLog is the base of every other part of PollPdmVault, so each part can
report progress. It declares the dependencies it reads; PollPdmVault's
constructor sets them.
"""

import time
from dataclasses import dataclass

from src.modules.external_data.domain.entities.pdm_sync_run import SYNC_RUN_RETENTION
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.ports.outbound.repositories.pdm_sync_run_repository import (
    IPdmSyncRunRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc

# Phases a poll run reports while it runs (PdmSyncRun.phase).
_PHASE_WALKING = "walking"
_PHASE_INGESTING = "ingesting"
_PHASE_FINISHING = "finishing"

# Minimum seconds between two live progress writes of one run.
_PROGRESS_INTERVAL_SECONDS = 2.0


@dataclass
class PollSummary:
    files_seen: int
    changed: int
    ingested: int
    skipped: int
    conflicts: int
    errors: int
    missing: int
    folders_walked: int
    # Cold-folder poll cadence (domain.services.pdm_poll_cadence): folders a
    # SCHEDULED run skipped entirely because they were not yet due, see
    # docs/reference/pdm-sync.md section 3. Always 0 on a MANUAL/INITIAL run,
    # both of which ignore cadence and walk every folder.
    folders_skipped_cold: int
    # Write-back to PDM (PdmWriteBack), tallied in memory as the run goes;
    # IPdmSyncRunRepository.add_entries only flushes rows, it never hands
    # them back for counting, so this is the only place that count lives
    # before _format_summary reads it.
    written_back: int
    # File type rule (docs/reference/pdm-documents.md section 1): a
    # made/bought/by_kind watched folder file whose extension is not
    # admitted for its (resolved) kind. It is never snapshotted, so this is
    # the only trace of it in a run.
    ignored_by_type: int
    # PdmDocumentSync (documents watched folders) and PdmThumbnails
    # (after a synced made/bought ingest), tallied the same way
    # `written_back` is.
    documents: int
    document_errors: int
    thumbnails: int
    # When live progress was last written (time.monotonic), shared by every
    # worker of the run so the writes stay throttled as a whole.
    progress_saved_at: float = 0.0


class PollRunLog:
    """Run bookkeeping; PollPdmVault sets every attribute declared here."""

    _runs: IPdmSyncRunRepository
    _uow: IUnitOfWork

    async def _save_progress(
        self, run: PdmSyncRun, summary: PollSummary, *, force: bool = False
    ) -> None:
        """Writes the run's live progress and running counts for the sync
        activity dialog, at most every few seconds unless `force`. Only
        called where this poller's session has no pending writes, so the
        commit carries nothing else."""
        now = time.monotonic()
        if not force and now - summary.progress_saved_at < _PROGRESS_INTERVAL_SECONDS:
            return
        summary.progress_saved_at = now
        self._copy_counts(run, summary)
        run.progress_at = now_utc()
        await self._runs.save_progress(run)
        await self._uow.commit()

    @staticmethod
    def _copy_counts(run: PdmSyncRun, summary: PollSummary) -> None:
        run.files_seen = summary.files_seen
        run.changed = summary.changed
        run.ingested = summary.ingested
        run.skipped = summary.skipped
        run.conflicts = summary.conflicts
        run.errors = summary.errors
        run.missing = summary.missing
        run.folders_walked = summary.folders_walked
        run.folders_skipped_cold = summary.folders_skipped_cold

    async def _finish_run(self, run: PdmSyncRun, summary: PollSummary, error: str | None) -> None:
        run.finished_at = now_utc()
        self._copy_counts(run, summary)
        run.phase = None
        run.current_path = None
        run.progress_at = run.finished_at
        run.error = error
        run.summary = self._format_summary(summary)
        await self._runs.finish(run)
        await self._uow.commit()
        await self._runs.prune(now_utc() - SYNC_RUN_RETENTION)
        await self._uow.commit()

    @staticmethod
    def _format_summary(summary: PollSummary) -> str:
        return (
            f"{summary.files_seen} files seen, {summary.changed} changed, "
            f"{summary.ingested} ingested, {summary.skipped} skipped, "
            f"{summary.conflicts} conflicts, {summary.errors} errors, "
            f"{summary.missing} missing, {summary.folders_walked} folders walked, "
            f"{summary.folders_skipped_cold} folders skipped (cold), "
            f"{summary.written_back} written back, "
            f"{summary.ignored_by_type} ignored by type, "
            f"{summary.documents} documents synced, {summary.document_errors} document errors, "
            f"{summary.thumbnails} thumbnails."
        )
