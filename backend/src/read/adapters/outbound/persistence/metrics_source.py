"""
SqlAlchemyRedisMetricsSource: IMetricsSource over event_outbox_table, the
Redis events stream, backup_runs, and the PDM sync run log/snapshot/folder
poll state tables: the data GladosStateCollector
(src/read/adapters/inbound/api/metrics.py) turns into gauges on every /metrics
scrape. See backup_last_success_ts/backup_last_failure_ts methods for the
backup gauges and the pdm_* methods below for the PDM gauges.

A SessionLocal() session is opened per DB-backed method call rather than
held on the instance: the collector runs once per scrape, on whichever
worker happened to answer it, so there is no request-scoped session to
reuse (unlike the ordinary get_db() dependency chain).

The Redis client below is dedicated to metrics collection, not
get_async_redis_client() (src/modules/platform/infrastructure/redis_client.py): that client's
timeouts and retry are sized for application traffic, longer than a scrape
should block against a hung Redis, same reasoning as readiness.py's
_get_readiness_redis_client, and deliberately not the same client instance,
so a slow metrics scrape and a slow readiness probe can't starve each
other's connection.
"""

from functools import lru_cache

import redis
import redis.asyncio
from sqlalchemy import func
from sqlalchemy import select

from src.modules.external_data.adapters.outbound.persistence.models.pdm_file_snapshot_model import (
    PdmFileSnapshotOrmModel,
)
from src.modules.external_data.adapters.outbound.persistence.models.pdm_folder_poll_state_model import (
    PdmFolderPollStateOrmModel,
)
from src.modules.external_data.adapters.outbound.persistence.models.pdm_reconciliation_finding_model import (
    PdmReconciliationFindingOrmModel,
)
from src.modules.external_data.adapters.outbound.persistence.models.pdm_sync_run_model import (
    PdmSyncRunOrmModel,
)
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.backup_run_model import (
    BackupRunOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.event_outbox_model import (
    EventOutboxOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.domain.value_objects.backup_run_status import BackupRunStatus
from src.modules.platform.infrastructure.events.registry import EVENTS_STREAM
from src.modules.platform.infrastructure.redis_client import new_probe_redis_client
from src.shared_kernel.domain.services.clock import now_utc

# Kept in sync by hand with the EventWorker(group=...) calls main.py's
# lifespan actually starts: there is no single shared constant for this
# list elsewhere in the codebase to import instead (see main.py's
# _handle_notification_event/_handle_webhook_event/_handle_auto_print_event/
# _handle_pdm_sync_event and the workers built around them).
_CONSUMER_GROUPS = ("notifications", "webhooks", "auto_print", "pdm_sync")


@lru_cache(maxsize=1)
def _get_metrics_redis_client() -> redis.asyncio.Redis:
    """The metrics collector's own Redis client, with the same 1s socket
    timeouts as readiness.py's probe client. Cached so repeated scrapes
    reuse one connection pool rather than opening a fresh TCP connection
    each time."""
    return new_probe_redis_client()


class SqlAlchemyRedisMetricsSource:
    """IMetricsSource. Every method may raise, see the port's docstring;
    GladosStateCollector.collect() decides what that means for the metric,
    not this class."""

    async def outbox_unpublished(self) -> int:
        async with SessionLocal() as db:
            return int(
                (
                    await db.execute(
                        select(func.count())
                        .select_from(EventOutboxOrmModel)
                        .where(EventOutboxOrmModel.published_at.is_(None))
                    )
                ).scalar_one()
            )

    async def event_stream_length(self) -> int:
        return int(await _get_metrics_redis_client().xlen(EVENTS_STREAM))

    async def event_stream_pending(self) -> dict[str, int]:
        client = _get_metrics_redis_client()
        pending: dict[str, int] = {}
        for group in _CONSUMER_GROUPS:
            try:
                summary = await client.xpending(EVENTS_STREAM, group)
            except redis.ResponseError as e:
                if "NOGROUP" in str(e):
                    # No consumer has ever started this group (fresh
                    # install, or dev without the lifespan running):
                    # that is zero pending, not a reason to drop the
                    # whole metric family the way a real Redis failure
                    # should (see the other branch, which re-raises).
                    continue
                raise
            pending[group] = int(summary["pending"])
        return pending

    async def backup_last_success_ts(self) -> float | None:
        return await self._backup_run_ts(BackupRunStatus.SUCCESS.value)

    async def backup_last_failure_ts(self) -> float | None:
        return await self._backup_run_ts(BackupRunStatus.FAILED.value)

    @staticmethod
    async def _backup_run_ts(status: str) -> float | None:
        """The finish time of the newest backup run with this status, newest
        by id as the backup history reads it."""
        async with SessionLocal() as db:
            finished_at = (
                await db.execute(
                    select(BackupRunOrmModel.finished_at)
                    .where(BackupRunOrmModel.status == status)
                    .order_by(BackupRunOrmModel.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            return finished_at.timestamp() if finished_at is not None else None

    async def pdm_last_poll_success_ts(self) -> float | None:
        return await self._pdm_scheduled_poll_ts(error=False)

    async def pdm_last_poll_failure_ts(self) -> float | None:
        return await self._pdm_scheduled_poll_ts(error=True)

    @staticmethod
    async def _pdm_scheduled_poll_ts(*, error: bool) -> float | None:
        async with SessionLocal() as db:
            error_filter = (
                PdmSyncRunOrmModel.error.is_not(None)
                if error
                else PdmSyncRunOrmModel.error.is_(None)
            )
            finished_at = (
                await db.execute(
                    select(PdmSyncRunOrmModel.finished_at)
                    .where(
                        PdmSyncRunOrmModel.trigger == PdmSyncTrigger.SCHEDULED.value,
                        error_filter,
                        PdmSyncRunOrmModel.finished_at.is_not(None),
                    )
                    .order_by(PdmSyncRunOrmModel.started_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            aware = utc_aware(finished_at)
            return aware.timestamp() if aware is not None else None

    async def pdm_last_trigger_ts(self) -> float | None:
        async with SessionLocal() as db:
            started_at = (
                await db.execute(
                    select(PdmSyncRunOrmModel.started_at)
                    .where(PdmSyncRunOrmModel.trigger == PdmSyncTrigger.FILE_TRIGGER.value)
                    .order_by(PdmSyncRunOrmModel.started_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            aware = utc_aware(started_at)
            return aware.timestamp() if aware is not None else None

    async def pdm_last_run_counters(self) -> dict[str, int] | None:
        async with SessionLocal() as db:
            run = (
                await db.execute(
                    select(PdmSyncRunOrmModel)
                    .where(PdmSyncRunOrmModel.finished_at.is_not(None))
                    .order_by(PdmSyncRunOrmModel.started_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if run is None:
                return None
            return {
                "files_seen": run.files_seen,
                "changed": run.changed,
                "ingested": run.ingested,
                "skipped": run.skipped,
                "conflicts": run.conflicts,
                "errors": run.errors,
                "missing": run.missing,
                "folders_walked": run.folders_walked,
                "folders_skipped_cold": run.folders_skipped_cold,
            }

    async def pdm_files_by_sync_state(self) -> dict[str, int]:
        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    select(PdmFileSnapshotOrmModel.sync_state, func.count()).group_by(
                        PdmFileSnapshotOrmModel.sync_state
                    )
                )
            ).all()
            return {sync_state: int(count) for sync_state, count in rows}

    async def pdm_reconciliation_findings_by_category(self) -> dict[str, int] | None:
        async with SessionLocal() as db:
            run_id = (
                await db.execute(
                    select(PdmSyncRunOrmModel.id)
                    .where(PdmSyncRunOrmModel.trigger == PdmSyncTrigger.RECONCILIATION.value)
                    .order_by(PdmSyncRunOrmModel.started_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if run_id is None:
                return None
            rows = (
                await db.execute(
                    select(
                        PdmReconciliationFindingOrmModel.category,
                        func.sum(PdmReconciliationFindingOrmModel.count),
                    )
                    .where(PdmReconciliationFindingOrmModel.run_id == run_id)
                    .group_by(PdmReconciliationFindingOrmModel.category)
                )
            ).all()
            return {category: int(total) for category, total in rows}

    async def pdm_folders_cold(self) -> int:
        async with SessionLocal() as db:
            now = now_utc()
            return int(
                (
                    await db.execute(
                        select(func.count())
                        .select_from(PdmFolderPollStateOrmModel)
                        .where(PdmFolderPollStateOrmModel.next_due_at > now)
                    )
                ).scalar_one()
            )
