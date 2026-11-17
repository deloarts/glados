"""
Return paginated metadata for all DB archives and file snapshots stored under
the configured backup_path, plus the run-history record from backup_runs:
last_run and the last 20 runs of either trigger, and the warnings the backup
configuration earns. Requires write:settings, raised from read:settings so
listing agrees with DownloadBackup, which is gated on write:settings because
a full DB dump exposes every password hash and TOTP secret. The list carries
no download URLs, so an archive leaves only through that authenticated
route.
"""

from __future__ import annotations

from src.modules.platform.application.dto.admin_settings_dto.storage import BackupEntryResult
from src.modules.platform.application.dto.admin_settings_dto.storage import BackupListResult
from src.modules.platform.application.dto.admin_settings_dto.storage import BackupRunEntryResult
from src.modules.platform.domain.entities.backup_run import BackupRun
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.services.backup_rules import backup_warnings
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.backup_run_repository import (
    IBackupRunRepository,
)
from src.modules.platform.ports.outbound.storage_port import IStorageAdapterFactory

_RUN_HISTORY_LIMIT = 20
_ARCHIVE_SUFFIXES = (".sql.gz.enc", ".sql.gz")


def _parse_timestamp(raw: str) -> str:
    """Convert filename timestamp 2026-07-13T02-00-00 → 2026-07-13T02:00:00."""
    if "T" in raw:
        date_part, time_part = raw.split("T", 1)
        return f"{date_part}T{time_part.replace('-', ':')}"
    return raw


def _archive_timestamp(filename: str) -> str:
    """The raw timestamp of an archive file name, for either format."""
    for suffix in _ARCHIVE_SUFFIXES:
        if filename.endswith(suffix):
            return filename.removesuffix(suffix)
    return filename


def _run_to_result(run: BackupRun) -> BackupRunEntryResult:
    return BackupRunEntryResult(
        slot=run.slot,
        trigger=run.trigger,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error=run.error,
    )


class ListBackups:
    def __init__(
        self,
        repo: IPlatformSettingsRepository,
        storage_factory: IStorageAdapterFactory,
        run_repo: IBackupRunRepository,
        *,
        encryption_key_configured: bool,
    ) -> None:
        self._repo = repo
        self._storage_factory = storage_factory
        self._run_repo = run_repo
        self._encryption_key_configured = encryption_key_configured

    async def execute(self, actor: User) -> BackupListResult:
        if not actor.has_permission(Permission.WRITE_SETTINGS):
            raise InsufficientPermissionsError("write:settings required.")

        runs = [_run_to_result(r) for r in await self._run_repo.latest(_RUN_HISTORY_LIMIT)]
        last_run = runs[0] if runs else None

        settings = await self._repo.get_storage()
        warnings = backup_warnings(
            settings, encryption_key_configured=self._encryption_key_configured
        )
        if not settings.backup_enabled or not settings.backup_path:
            return BackupListResult(
                db=[], files=[], warnings=warnings, last_run=last_run, runs=runs
            )

        storage = self._storage_factory(settings)
        backup_prefix = settings.backup_path.rstrip("/")

        # ── DB archives ───────────────────────────────────────
        db_prefix = f"{backup_prefix}/db/"
        db_keys = sorted(await storage.list_keys(db_prefix), reverse=True)
        db_entries: list[BackupEntryResult] = []
        for key in db_keys:
            filename = key.rsplit("/", 1)[-1]  # 2026-07-13T02-00-00.sql.gz.enc
            db_entries.append(
                BackupEntryResult(
                    key=key,
                    timestamp=_parse_timestamp(_archive_timestamp(filename)),
                    encrypted=filename.endswith(".sql.gz.enc"),
                )
            )

        # ── File snapshots ─────────────────────────────────────
        files_prefix = f"{backup_prefix}/files/"
        all_file_keys = await storage.list_keys(files_prefix)
        snapshot_timestamps: set[str] = set()
        for key in all_file_keys:
            rel = key[len(files_prefix) :]
            segment = rel.split("/")[0]
            if segment:
                snapshot_timestamps.add(segment)

        file_entries: list[BackupEntryResult] = []
        for ts in sorted(snapshot_timestamps, reverse=True):
            snapshot_key = f"{files_prefix}{ts}"
            file_entries.append(
                BackupEntryResult(key=snapshot_key, timestamp=_parse_timestamp(ts), encrypted=False)
            )

        return BackupListResult(
            db=db_entries, files=file_entries, warnings=warnings, last_run=last_run, runs=runs
        )
