"""
Unit tests for RequestPdmFileRefresh: the API-key trigger endpoint's use
case. There is no database and no HTTP: the event bus and unit of work are the
shared fakes, everything else is a small local fake.
"""

from typing import Any

import pytest

from src.modules.external_data.application.dto.pdm_dto import PdmChangedFileRef
from src.modules.external_data.application.dto.pdm_dto import RequestPdmFileRefreshBatchCommand
from src.modules.external_data.application.dto.pdm_dto import RequestPdmFileRefreshCommand
from src.modules.external_data.application.services.pdm_trigger_rate_limiter import (
    PdmTriggerRateLimiter,
)
from src.modules.external_data.application.use_cases.pdm.request_pdm_file_refresh import (
    RequestPdmFileRefresh,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.errors import PdmNotEnabledError
from src.modules.external_data.domain.errors import PdmTriggerRateLimitedError
from src.modules.external_data.domain.errors import PdmVaultMismatchError
from src.modules.external_data.domain.events.pdm_events import PdmFileChangeRequested
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests import factories
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork


def make_user(*, permissions: list[str] | None = None, **overrides: Any) -> User:
    """A user who may trigger a PDM sync unless the test passes other permissions."""
    if permissions is None:
        permissions = [Permission.USE_PDM_ADDIN]
    return factories.make_user(permissions=permissions, **overrides)


def make_pdm_settings(**overrides: object) -> AdminPdmSettings:
    defaults: dict[str, object] = dict(
        id=1,
        made_item_variable_map={},
        bought_item_variable_map={},
        enabled=True,
        base_url="http://pdm-host:65453",
        vault_name="MyVault",
        username="svc-account",
        password="secret",
        verify_certificate=True,
        timeout_seconds=15,
        session_token=None,
        session_user_id=None,
        session_obtained_at=None,
        watched_folders=[],
        made_released_state_ids=[10],
        made_obsolete_state_ids=[20],
        made_replaced_state_ids=[20],
        bought_released_state_ids=[10],
        bought_obsolete_state_ids=[20],
        bought_replaced_state_ids=[20],
        poll_interval_minutes=15,
        vault_id="",
        cad_items_read_only=True,
        last_poll_at=None,
        last_poll_error=None,
        last_poll_summary=None,
        writeback_enabled=False,
        made_item_extensions=["sldprt"],
        bought_item_extensions=["sldprt", "sldasm"],
        document_categories={"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
        thumbnails_enabled=False,
        stuck_after_days=7,
        reconcile_requested_deep=None,
        required_fields={"made": [], "bought": []},
    )
    defaults.update(overrides)
    return AdminPdmSettings(**defaults)  # type: ignore[arg-type]


class FakeAdminSettingsRepository:
    def __init__(self, pdm: AdminPdmSettings) -> None:
        self._pdm = pdm

    async def get_pdm(self) -> AdminPdmSettings:
        return self._pdm


def make_command(**overrides: object) -> RequestPdmFileRefreshCommand:
    defaults: dict[str, object] = dict(vault_name="MyVault", file_id=100, path=None, version=None)
    defaults.update(overrides)
    return RequestPdmFileRefreshCommand(**defaults)  # type: ignore[arg-type]


class TestPermission:
    async def test_actor_without_permission_is_rejected(self) -> None:
        repo = FakeAdminSettingsRepository(make_pdm_settings())
        bus = FakeEventBus()
        uow = FakeUnitOfWork()
        use_case = RequestPdmFileRefresh(repo, bus, uow, PdmTriggerRateLimiter())

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(make_user(permissions=[]), make_command())

        assert bus.published == []
        assert not uow.committed


class TestNotEnabled:
    async def test_disabled_integration_raises(self) -> None:
        repo = FakeAdminSettingsRepository(make_pdm_settings(enabled=False))
        bus = FakeEventBus()
        uow = FakeUnitOfWork()
        use_case = RequestPdmFileRefresh(repo, bus, uow, PdmTriggerRateLimiter())

        with pytest.raises(PdmNotEnabledError):
            await use_case.execute(make_user(), make_command())

    async def test_unconfigured_integration_raises(self) -> None:
        repo = FakeAdminSettingsRepository(make_pdm_settings(password=None))
        bus = FakeEventBus()
        uow = FakeUnitOfWork()
        use_case = RequestPdmFileRefresh(repo, bus, uow, PdmTriggerRateLimiter())

        with pytest.raises(PdmNotEnabledError):
            await use_case.execute(make_user(), make_command())


class TestVaultName:
    async def test_wrong_vault_name_raises_value_error(self) -> None:
        repo = FakeAdminSettingsRepository(make_pdm_settings(vault_name="MyVault"))
        bus = FakeEventBus()
        uow = FakeUnitOfWork()
        use_case = RequestPdmFileRefresh(repo, bus, uow, PdmTriggerRateLimiter())

        with pytest.raises(PdmVaultMismatchError, match="Unknown vault"):
            await use_case.execute(make_user(), make_command(vault_name="OtherVault"))

    async def test_vault_name_matches_case_insensitively(self) -> None:
        repo = FakeAdminSettingsRepository(make_pdm_settings(vault_name="MyVault"))
        bus = FakeEventBus()
        uow = FakeUnitOfWork()
        use_case = RequestPdmFileRefresh(repo, bus, uow, PdmTriggerRateLimiter())

        await use_case.execute(make_user(), make_command(vault_name="myvault"))

        assert len(bus.published) == 1


class TestRateLimit:
    async def test_exceeding_the_budget_raises(self) -> None:
        repo = FakeAdminSettingsRepository(make_pdm_settings())
        bus = FakeEventBus()
        uow = FakeUnitOfWork()
        limiter = PdmTriggerRateLimiter(max_requests=2, window_seconds=60.0)
        use_case = RequestPdmFileRefresh(repo, bus, uow, limiter)
        user = make_user()

        await use_case.execute(user, make_command())
        await use_case.execute(user, make_command())

        with pytest.raises(PdmTriggerRateLimitedError):
            await use_case.execute(user, make_command())

        assert len(bus.published) == 2

    async def test_the_budget_is_tracked_per_actor(self) -> None:
        repo = FakeAdminSettingsRepository(make_pdm_settings())
        bus = FakeEventBus()
        uow = FakeUnitOfWork()
        limiter = PdmTriggerRateLimiter(max_requests=1, window_seconds=60.0)
        use_case = RequestPdmFileRefresh(repo, bus, uow, limiter)

        await use_case.execute(make_user(id=1), make_command())
        # A different actor id has its own, untouched budget.
        await use_case.execute(make_user(id=2), make_command())

        assert len(bus.published) == 2


class TestPublishing:
    async def test_success_publishes_and_commits(self) -> None:
        repo = FakeAdminSettingsRepository(make_pdm_settings(vault_name="MyVault"))
        bus = FakeEventBus()
        uow = FakeUnitOfWork()
        use_case = RequestPdmFileRefresh(repo, bus, uow, PdmTriggerRateLimiter())
        user = make_user(id=7)

        await use_case.execute(user, make_command(file_id=555, path=None, version=3))

        assert uow.committed
        assert len(bus.published) == 1
        event = bus.published[0]
        assert isinstance(event, PdmFileChangeRequested)
        assert event.vault_name == "MyVault"
        assert event.file_id == 555
        assert event.path is None
        assert event.version == 3
        assert event.requested_by_id == 7

    async def test_success_by_path(self) -> None:
        repo = FakeAdminSettingsRepository(make_pdm_settings())
        bus = FakeEventBus()
        uow = FakeUnitOfWork()
        use_case = RequestPdmFileRefresh(repo, bus, uow, PdmTriggerRateLimiter())

        await use_case.execute(make_user(), make_command(file_id=None, path="\\Made\\part.sldprt"))

        event = bus.published[0]
        assert event.file_id is None
        assert event.path == "\\Made\\part.sldprt"


def make_batch(*refs: tuple[int, int | None]) -> RequestPdmFileRefreshBatchCommand:
    return RequestPdmFileRefreshBatchCommand(
        vault_name="MyVault",
        files=[PdmChangedFileRef(file_id=file_id, version=version) for file_id, version in refs],
    )


class TestBatch:
    async def test_publishes_one_event_per_distinct_file_and_commits_once(self) -> None:
        bus = FakeEventBus()
        uow = FakeUnitOfWork()
        use_case = RequestPdmFileRefresh(
            FakeAdminSettingsRepository(make_pdm_settings()), bus, uow, PdmTriggerRateLimiter()
        )

        accepted = await use_case.execute_batch(make_user(), make_batch((1, 3), (2, None), (1, 4)))

        assert accepted == 2
        assert uow.committed
        events = [e for e in bus.published if isinstance(e, PdmFileChangeRequested)]
        assert [(e.file_id, e.version) for e in events] == [(1, 4), (2, None)]
        assert all(e.source == "file_trigger" for e in events)

    async def test_rate_limit_counts_every_file(self) -> None:
        bus = FakeEventBus()
        limiter = PdmTriggerRateLimiter(max_requests=3, window_seconds=60.0)
        use_case = RequestPdmFileRefresh(
            FakeAdminSettingsRepository(make_pdm_settings()), bus, FakeUnitOfWork(), limiter
        )
        user = make_user()

        await use_case.execute_batch(user, make_batch((1, None), (2, None)))
        with pytest.raises(PdmTriggerRateLimitedError):
            await use_case.execute_batch(user, make_batch((3, None), (4, None)))
        await use_case.execute(user, make_command(file_id=5))

        assert [e.file_id for e in bus.published] == [1, 2, 5]

    async def test_wrong_vault_raises_before_publishing(self) -> None:
        bus = FakeEventBus()
        use_case = RequestPdmFileRefresh(
            FakeAdminSettingsRepository(make_pdm_settings()),
            bus,
            FakeUnitOfWork(),
            PdmTriggerRateLimiter(),
        )
        cmd = make_batch((1, None)).model_copy(update={"vault_name": "Other"})

        with pytest.raises(PdmVaultMismatchError, match="Unknown vault"):
            await use_case.execute_batch(make_user(), cmd)

        assert bus.published == []
