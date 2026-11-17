"""
Admin settings endpoints for the Storage tab's connection settings and the
storage migration. Backup run and restore endpoints live in backup.py, next to
it. All reads require read:settings; all writes require write:settings.

The migration also runs as a background task behind an SSE stream, shaped like
Auto-Plan's (endpoints/production_schedule.py): the task owns its session and
keeps copying when the client goes away, a Redis mutex allows one migration at
a time, and a status endpoint lets a reloaded page find a running one.
"""

import asyncio

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter
from sse_starlette.sse import EventSourceResponse

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_storage_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_test_storage_connection_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_update_storage_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.storage import build_migrate_storage_use_case
from src.modules.platform.adapters.inbound.api.deps.storage import get_migrate_storage_use_case
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.storage import (
    AdminStorageSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.storage import (
    StorageMigrationResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.storage import (
    StorageMigrationRunResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.storage import (
    StorageMigrationStatusResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.storage import (
    UpdateStorageSettingsRequest,
)
from src.modules.platform.adapters.inbound.api.streamed_run import StreamedRun
from src.modules.platform.application.dto.admin_settings_dto.storage import (
    AdminStorageSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.storage import StorageMigrationProgress
from src.modules.platform.application.dto.admin_settings_dto.storage import StorageMigrationResult
from src.modules.platform.application.dto.admin_settings_dto.storage import (
    UpdateStorageSettingsCommand,
)
from src.modules.platform.application.use_cases.admin_settings.get_storage_settings import (
    GetStorageSettings,
)
from src.modules.platform.application.use_cases.admin_settings.migrate_storage import MigrateStorage
from src.modules.platform.application.use_cases.admin_settings.test_storage_connection import (
    TestStorageConnection,
)
from src.modules.platform.application.use_cases.admin_settings.update_storage_settings import (
    UpdateStorageSettings,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import StorageMigrationInProgressError
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure import storage_migration_run_registry as migration_registry
from src.modules.platform.infrastructure.run_registry import update_snapshot

router = APIRouter()

# Strong references to every running migration task. The event loop only
# holds weak references, so a run whose client disconnected could otherwise
# be garbage-collected mid-copy.
_RUN_TASKS: set[asyncio.Task[None]] = set()


@router.get("/storage", response_model=AdminStorageSettingsResponse)
async def get_storage_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetStorageSettings = Depends(get_storage_settings_use_case),
) -> AdminStorageSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/storage", response_model=AdminStorageSettingsResponse)
async def update_storage_settings(
    body: UpdateStorageSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateStorageSettings = Depends(get_update_storage_settings_use_case),
) -> AdminStorageSettingsResult:
    """Update the file storage and backup settings. A changed backup schedule
    takes effect within a minute. Requires write:settings."""
    # BackupScheduler's tick re-reads these settings every 60 s, so nothing
    # needs reconfiguring here.
    cmd = UpdateStorageSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.post("/storage/test", status_code=status.HTTP_204_NO_CONTENT)
async def test_storage_connection(
    body: UpdateStorageSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: TestStorageConnection = Depends(get_test_storage_connection_use_case),
) -> None:
    """Test connectivity to the storage backend using the supplied settings.
    Returns 204 on success, 400 with an error detail on failure.
    Requires write:settings."""
    cmd = UpdateStorageSettingsCommand(**body.model_dump())
    await use_case.execute(actor=actor, cmd=cmd)


@router.post("/storage/migrate", response_model=StorageMigrationResponse)
async def migrate_storage(
    body: UpdateStorageSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: MigrateStorage = Depends(get_migrate_storage_use_case),
) -> StorageMigrationResult:
    """Copy all objects from the current provider to the new provider, then switch.
    Only commits the new settings when every file copies without error.
    Requires write:settings. The request lasts as long as the copy, so a
    proxy in front may give up on it; the migration dialog uses the
    streaming variant below."""
    cmd = UpdateStorageSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.post("/storage/migrate/stream")
async def migrate_storage_stream(
    body: UpdateStorageSettingsRequest,
    actor: User = Depends(get_current_active_user),
) -> EventSourceResponse:
    """Streaming variant of `POST /storage/migrate` with the same input and
    outcome: a `progress` frame before each object is copied (`current`,
    `total`, `key`), then exactly one `result` frame (the plain endpoint's
    response body) or `error` frame. Requires write:settings.

    The copy runs in its own task with its own session, because FastAPI
    closes this request's session before the stream sends its first byte. A
    client disconnect only ends the stream: the task keeps copying and still
    switches the settings once every object is copied, or leaves them as
    they were. A server shutdown cancels the task before that final commit,
    which leaves the settings unchanged too; copied objects are overwritten
    on the next attempt.

    A second migration while one holds the Redis mutex gets a 409 before any
    stream is opened. The heartbeat keeps the mutex alive and stores the
    progress snapshot for GET /storage/migrate/status."""
    # Checked before the response starts, so a forbidden caller gets a
    # plain 403 instead of an error frame.
    assert_has_permission(actor, Permission.WRITE_SETTINGS, "migrate", "storage")
    cmd = UpdateStorageSettingsCommand(**body.model_dump())

    run: StreamedRun[StorageMigrationProgress] = StreamedRun(
        label="Storage migration",
        execute=lambda db, progress: build_migrate_storage_use_case(db).execute(
            actor=actor, cmd=cmd, progress=progress
        ),
        response_model=StorageMigrationResponse,
        snapshot=lambda handle, event: update_snapshot(
            handle, "copying", event.current, event.total, event.key
        ),
        heartbeat_once=migration_registry.heartbeat_once,
        release=migration_registry.release,
    )

    handle = await migration_registry.try_acquire(actor.id, actor.full_name or actor.username)
    if handle is None:
        raise StorageMigrationInProgressError(
            "Another storage migration is already running. Try again once it finishes."
        )

    # Not awaited, so a client disconnect never aborts the copy.
    return await run.start(handle, _RUN_TASKS)


@router.get("/storage/migrate/status", response_model=StorageMigrationStatusResponse)
async def storage_migration_status(
    actor: User = Depends(get_current_active_user),
) -> StorageMigrationStatusResponse:
    """The running migration, if any, for clients that are not its runner: a
    reloaded Storage tab, or a dialog whose stream dropped. Requires
    read:settings."""
    assert_has_permission(actor, Permission.READ_SETTINGS, "read", "storage settings")
    state = await migration_registry.read()
    run = (
        StorageMigrationRunResponse.model_validate(state, from_attributes=True)
        if state is not None
        else None
    )
    return StorageMigrationStatusResponse(running=run is not None, run=run)
