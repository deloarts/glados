"""
Admin settings endpoints for the Backups tab: listing, downloading, running
now, and restoring files. All reads require read:settings; all writes
require write:settings (a full DB dump exposes every password hash and
TOTP secret, more than a settings read implies).
"""

from collections.abc import Awaitable
from collections.abc import Callable

from fastapi import BackgroundTasks
from fastapi import Depends
from fastapi import Response
from fastapi import status
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.backup import get_download_backup_use_case
from src.modules.platform.adapters.inbound.api.deps.backup import get_list_backups_use_case
from src.modules.platform.adapters.inbound.api.deps.backup import get_restore_files_use_case
from src.modules.platform.adapters.inbound.api.deps.backup import get_run_backup_now_use_case
from src.modules.platform.adapters.inbound.api.deps.backup import get_run_claimed_backup_factory
from src.modules.platform.adapters.inbound.api.download_headers import build_download_headers
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.storage import (
    BackupListResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.storage import (
    RestoreFilesRequest,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.storage import (
    RestoreFilesResponse,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.application.dto.admin_settings_dto.storage import BackupListResult
from src.modules.platform.application.dto.admin_settings_dto.storage import RestoreFilesResult
from src.modules.platform.application.use_cases.admin_settings.download_backup import DownloadBackup
from src.modules.platform.application.use_cases.admin_settings.list_backups import ListBackups
from src.modules.platform.application.use_cases.admin_settings.restore_files import RestoreFiles
from src.modules.platform.application.use_cases.admin_settings.run_backup_now import RunBackupNow
from src.modules.platform.application.use_cases.backup.run_claimed_backup import RunClaimedBackup
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.process_identity import worker_identity

router = APIRouter()


@router.get("/storage/backups", response_model=BackupListResponse)
async def list_backups(
    actor: User = Depends(get_current_active_user),
    use_case: ListBackups = Depends(get_list_backups_use_case),
) -> BackupListResult:
    """List available DB archives and file snapshots, plus the run-history
    record (last_run, runs). Requires write:settings."""
    return await use_case.execute(actor=actor)


@router.get("/storage/backups/download")
async def download_backup(
    key: str,
    actor: User = Depends(get_current_active_user),
    use_case: DownloadBackup = Depends(get_download_backup_use_case),
) -> Response:
    """Stream a single DB archive or file-snapshot object's raw bytes.
    Requires write:settings: a full DB dump exposes every password hash
    and TOTP secret, more than a settings read implies."""
    stream = await use_case.execute(actor=actor, key=key)
    file_name = key.rsplit("/", 1)[-1]
    headers = build_download_headers(file_name, content_type=stream.content_type)
    if stream.size is not None:
        headers["Content-Length"] = str(stream.size)
    return StreamingResponse(stream.chunks, media_type=stream.content_type, headers=headers)


@router.post("/storage/backups/run-now", status_code=status.HTTP_202_ACCEPTED)
async def run_backup_now(
    background_tasks: BackgroundTasks,
    actor: User = Depends(get_current_active_user),
    use_case: RunBackupNow = Depends(get_run_backup_now_use_case),
    run_claimed_backup_factory: Callable[[AsyncSession], Awaitable[RunClaimedBackup]] = Depends(
        get_run_claimed_backup_factory
    ),
) -> None:
    """Start a backup run in the background. 409 while another run is still
    running. Requires write:settings."""
    # The run is claimed synchronously so the 202 or 409 answer is accurate.
    # Only the dump and upload (RunClaimedBackup, the same lock-guarded path a
    # scheduled run takes) move to the background task, on a fresh session,
    # because the request's session may be closed by then.
    run = await use_case.execute(actor=actor, worker=worker_identity())

    async def _do_backup() -> None:
        async with SessionLocal() as db:
            backup = await run_claimed_backup_factory(db)
            await backup.execute(run.id)

    background_tasks.add_task(_do_backup)


@router.post("/storage/backups/files/restore", response_model=RestoreFilesResponse)
async def restore_files(
    body: RestoreFilesRequest,
    actor: User = Depends(get_current_active_user),
    use_case: RestoreFiles = Depends(get_restore_files_use_case),
) -> RestoreFilesResult:
    """Restore all files from a snapshot back to active storage. Requires write:settings."""
    return await use_case.execute(actor=actor, snapshot_key=body.snapshot_key)
