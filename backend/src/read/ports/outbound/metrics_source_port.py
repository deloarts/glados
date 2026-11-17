"""
The application-state facts `GET /metrics` publishes as gauges, behind a
port so the collector (metrics.py's GladosStateCollector) never imports
SQLAlchemy models or a Redis client. Every method may raise; the collector
decides per metric what a failure means for the scrape.
"""

from typing import Protocol
from typing import runtime_checkable


@runtime_checkable
class IMetricsSource(Protocol):
    async def outbox_unpublished(self) -> int:
        """Rows in event_outbox_table not yet relayed to the events
        stream (published_at IS NULL): a growing number means the relay
        is stuck or Redis is down."""
        ...

    async def event_stream_length(self) -> int:
        """XLEN of the glados:events stream (registry.EVENTS_STREAM)."""
        ...

    async def event_stream_pending(self) -> dict[str, int]:
        """XPENDING summary count per consumer group, keyed by group name.
        A group with no consumer started yet is simply absent from the
        result, not an error."""
        ...

    async def backup_last_success_ts(self) -> float | None:
        """Unix timestamp of the most recent successful backup run, or
        None if there has never been one."""
        ...

    async def backup_last_failure_ts(self) -> float | None:
        """Unix timestamp of the most recent failed backup run, or None
        if there has never been one."""
        ...

    async def pdm_last_poll_success_ts(self) -> float | None:
        """Unix timestamp of `finished_at` for the newest scheduled PDM
        poll (PdmSyncTrigger.SCHEDULED) that finished with `error IS
        NULL`, or None if there has never been one."""
        ...

    async def pdm_last_poll_failure_ts(self) -> float | None:
        """Unix timestamp of `finished_at` for the newest scheduled PDM
        poll that finished with `error IS NOT NULL`, or None if there has
        never been one."""
        ...

    async def pdm_last_trigger_ts(self) -> float | None:
        """Unix timestamp of `started_at` for the newest run with trigger
        PdmSyncTrigger.FILE_TRIGGER: the add-in's change-notification
        endpoint, and the closest thing to an "add-in is alive" signal
        this port has. None if the add-in has never triggered a sync."""
        ...

    async def pdm_last_run_counters(self) -> dict[str, int] | None:
        """The counter columns of the newest finished PDM sync run, any
        trigger: files_seen, changed, ingested, skipped, conflicts,
        errors, missing, folders_walked, folders_skipped_cold. None if no
        run has ever finished."""
        ...

    async def pdm_files_by_sync_state(self) -> dict[str, int]:
        """pdm_file_snapshot row counts grouped by sync_state, keyed by
        the PdmFileSyncState value. A state with no rows is simply absent
        from the result, not an error: the collector zero-fills every
        enum value from this."""
        ...

    async def pdm_reconciliation_findings_by_category(self) -> dict[str, int] | None:
        """Finding counts per category (summed, not row-counted) of the
        newest PdmSyncRun with trigger PdmSyncTrigger.RECONCILIATION,
        keyed by the PdmReconciliationCategory value. None if a
        reconciliation run has never been recorded; a category with no
        findings on that run is simply absent, the collector zero-fills
        the rest."""
        ...

    async def pdm_folders_cold(self) -> int:
        """Count of pdm_folder_poll_state rows whose next_due_at is
        still in the future: watched folders the cold-folder cadence is
        currently backing off, not due for another walk yet."""
        ...
