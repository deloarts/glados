"""
PollPdmVault runs every PDM Web API request through a real
PdmSessionService wired with the poll's own unit of work. The run must
never reach `call` with staged writes on the shared session, since the
session's pre-request commit (and any token refresh) would persist them
half done, and every gateway request must follow that commit, so no
pooled connection sits in an open transaction for the HTTP wait.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from typing import Any

from src.modules.external_data.application.dto.pdm_dto import IngestOutcome
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRunEntry
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConnection
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from tests.unit.poll_pdm_vault._helpers import MADE_FOLDER_ID
from tests.unit.poll_pdm_vault._helpers import WRITE_BACK_VAR_MAP
from tests.unit.poll_pdm_vault._helpers import make_object
from tests.unit.poll_pdm_vault._helpers import make_pdm_settings
from tests.unit.poll_pdm_vault.rig import Rig

_GATEWAY_METHODS = (
    "browse_folder",
    "files_info",
    "file_variables",
    "vault_info",
    "get_datacard",
    "set_datacard_variables",
)


class PendingWritesTracker:
    """IUnitOfWork fake that knows whether a write is staged: wrapped
    repository writes mark it dirty, commit and rollback clear it."""

    def __init__(self) -> None:
        self.pending = False
        self.events: list[str] = []

    def stage(self, what: str) -> None:
        self.pending = True
        self.events.append(f"write:{what}")

    async def commit(self) -> None:
        self.pending = False
        self.events.append("commit")

    async def rollback(self) -> None:
        self.pending = False
        self.events.append("rollback")


def _track_writes(target: object, method: str, tracker: PendingWritesTracker) -> None:
    original = getattr(target, method)

    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = await original(*args, **kwargs)
        tracker.stage(method)
        return result

    setattr(target, method, wrapper)


def _track_gateway(gateway: object, tracker: PendingWritesTracker, order: list[str]) -> None:
    """Records, for every gateway request, the tracker event right before
    it; the session's own release commit must be that event."""
    for method in _GATEWAY_METHODS:
        original = getattr(gateway, method)

        def make(name: str, fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                previous = tracker.events[-1] if tracker.events else "none"
                order.append(f"{name} after {previous}")
                return await fn(*args, **kwargs)

            return wrapper

        setattr(gateway, method, make(method, original))


class CheckingSessionService(PdmSessionService):
    """Records whether writes were pending when `call` was entered, before
    the service's own release commit can hide them."""

    def __init__(self, tracker: PendingWritesTracker, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._tracker = tracker
        self.pending_at_call: list[bool] = []

    async def call(self, fn: Callable[[IPdmGateway, str], Awaitable[Any]]) -> Any:
        self.pending_at_call.append(self._tracker.pending)
        return await super().call(fn)


class WritingThumbnails:
    """Stands in for PdmThumbnails: one PDM request, then a staged run
    entry, the same shape the real service has."""

    def __init__(self, session: PdmSessionService, rig: Rig) -> None:
        self._session = session
        self._rig = rig

    async def after_ingest(
        self, vault_id: str, file: PdmObjectInfo, kind: str, outcome: IngestOutcome, run: PdmSyncRun
    ) -> str | None:
        async def _do(gw: IPdmGateway, token: str) -> list[PdmObjectInfo]:
            return await gw.files_info(token, [file.id])

        await self._session.call(_do)
        await self._rig.run_repo.add_entries(
            run.id,
            [
                PdmSyncRunEntry(
                    id=0,
                    run_id=run.id,
                    vault_id=vault_id,
                    file_id=file.id,
                    name=file.name,
                    path=file.path,
                    kind=kind,
                    action="thumbnail",
                    item_id=outcome.item_id,
                    message="stored thumbnail",
                    created_at=datetime.now(UTC),
                )
            ],
        )
        return "thumbnail"


def _wire(rig: Rig) -> tuple[CheckingSessionService, PendingWritesTracker, list[str]]:
    tracker = PendingWritesTracker()
    order: list[str] = []
    for repo, method in (
        (rig.run_repo, "add_entries"),
        (rig.snapshot_repo, "upsert_many"),
        (rig.made_item_repo, "save"),
        (rig.bought_item_repo, "save"),
        (rig.folder_poll_state_repo, "upsert"),
        (rig.folder_poll_state_repo, "reset"),
    ):
        _track_writes(repo, method, tracker)
    _track_gateway(rig.gateway, tracker, order)

    def factory(connection: PdmConnection) -> IPdmGateway:
        return rig.gateway  # type: ignore[return-value]

    session = CheckingSessionService(
        tracker,
        repo=rig.admin_settings_repo,
        gateway_factory=factory,
        uow=tracker,
    )
    rig.uow = tracker  # type: ignore[assignment]
    rig.thumbnails = WritingThumbnails(session, rig)  # type: ignore[assignment]
    rig.rebuild(session)
    return session, tracker, order


async def test_no_pdm_request_starts_with_pending_writes_or_an_open_transaction() -> None:
    settings = make_pdm_settings(
        writeback_enabled=True,
        made_item_variable_map=dict(WRITE_BACK_VAR_MAP),
        session_token="stored-token",
        session_obtained_at=datetime.now(UTC),
    )
    rig = Rig(settings=settings)
    rig.gateway.folders[MADE_FOLDER_ID] = [make_object(id=1), make_object(id=2)]
    rig.gateway.by_id = {1: make_object(id=1), 2: make_object(id=2)}
    session, tracker, order = _wire(rig)

    summary = await rig.use_case.execute()

    assert summary.ingested == 2
    assert summary.written_back == 2
    assert summary.thumbnails == 2
    # Two browses (the name walk to the folder, then the folder itself),
    # then per file: variables, datacard, set and the thumbnail lookup.
    assert len(session.pending_at_call) == 10
    assert session.pending_at_call == [False] * len(session.pending_at_call)
    assert order
    assert all(entry.endswith("after commit") for entry in order), order
    actions = [e.action for e in rig.run_repo.entries[1]]
    assert actions.count("writeback") == 2
    assert actions.count("thumbnail") == 2
    assert "commit" in tracker.events
