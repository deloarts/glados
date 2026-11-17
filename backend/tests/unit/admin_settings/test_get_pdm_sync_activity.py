"""
GetPdmSyncActivity: the requested flag, which unfinished run counts as
running, and the permission check.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest

from src.modules.external_data.application.use_cases.admin_settings.get_pdm_sync_activity import (
    GetPdmSyncActivity,
)
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.admin_settings.fakes import FakeAdminSettingsRepository


def _run(*, progress_at: datetime | None) -> PdmSyncRun:
    started = datetime.now(UTC) - timedelta(minutes=1)
    return PdmSyncRun(
        id=1,
        started_at=started,
        finished_at=None,
        trigger=PdmSyncTrigger.MANUAL,
        files_seen=0,
        changed=0,
        ingested=0,
        skipped=0,
        conflicts=0,
        errors=0,
        missing=0,
        error=None,
        summary=None,
        folders_walked=0,
        phase="walking",
        progress_at=progress_at,
    )


class _Runs:
    def __init__(self, unfinished: PdmSyncRun | None) -> None:
        self._unfinished = unfinished

    async def latest_unfinished(self, triggers: list[str]) -> PdmSyncRun | None:
        return self._unfinished

    async def recent_entries(self, limit: int) -> list:
        return []


def _use_case(*, enabled: bool, last_poll_at: datetime | None, run: PdmSyncRun | None):
    repo = FakeAdminSettingsRepository()
    repo.pdm.enabled = enabled
    repo.pdm.last_poll_at = last_poll_at
    return GetPdmSyncActivity(repo, _Runs(run))  # type: ignore[arg-type]


READER = make_user(permissions=[Permission.READ_SETTINGS])


class TestGetPdmSyncActivity:
    async def test_cleared_last_poll_without_a_run_is_requested(self):
        result = await _use_case(enabled=True, last_poll_at=None, run=None).execute(READER)
        assert result.requested is True
        assert result.run is None

    async def test_running_poll_is_reported_and_not_requested(self):
        run = _run(progress_at=datetime.now(UTC))
        result = await _use_case(enabled=True, last_poll_at=None, run=run).execute(READER)
        assert result.requested is False
        assert result.run is not None
        assert result.run.phase == "walking"

    async def test_run_whose_progress_stopped_long_ago_is_not_running(self):
        run = _run(progress_at=datetime.now(UTC) - timedelta(hours=1))
        result = await _use_case(enabled=True, last_poll_at=datetime.now(UTC), run=run).execute(
            READER
        )
        assert result.run is None

    async def test_disabled_integration_is_never_requested(self):
        result = await _use_case(enabled=False, last_poll_at=None, run=None).execute(READER)
        assert result.requested is False

    async def test_requires_read_settings(self):
        with pytest.raises(InsufficientPermissionsError):
            await _use_case(enabled=True, last_poll_at=None, run=None).execute(
                make_user(permissions=[])
            )
