"""
Rig bundles every fake plus a wired PollPdmVault (and its own PdmWriteBack,
inert by default) for one test. Used by every test module in this package.
"""

import dataclasses
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.external_data.application.dto.pdm_dto import IngestOutcome
from src.modules.external_data.application.dto.pdm_dto import PdmFilePayload
from src.modules.external_data.application.services.pdm_writeback import PdmWriteBack
from src.modules.external_data.application.use_cases.pdm.poll_pdm_vault import PollPdmVault
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.entities.pdm_folder_poll_state import PdmFolderPollState
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRunEntry
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConfigVariables
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCard
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmVaultInfo
from src.shared_kernel.domain.services.clock import now_utc
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.poll_pdm_vault._helpers import BOUGHT_FOLDER_ID
from tests.unit.poll_pdm_vault._helpers import BY_KIND_FOLDER_ID
from tests.unit.poll_pdm_vault._helpers import MADE_FOLDER_ID
from tests.unit.poll_pdm_vault._helpers import ROOT_ID
from tests.unit.poll_pdm_vault._helpers import make_folder
from tests.unit.poll_pdm_vault._helpers import make_pdm_settings
from tests.unit.poll_pdm_vault._helpers import make_write_back_card


class FakeAdminSettingsRepository:
    def __init__(self, pdm: AdminPdmSettings) -> None:
        self._pdm = pdm
        self.poll_status_calls: list[tuple[datetime, str | None, str | None]] = []

    async def get_pdm(self) -> AdminPdmSettings:
        return self._pdm

    async def save_pdm_vault_id(self, vault_id: str) -> None:
        self._pdm.vault_id = vault_id

    async def save_pdm_poll_status(
        self, *, at: datetime, error: str | None, summary: str | None
    ) -> None:
        self.poll_status_calls.append((at, error, summary))


class FakeGateway:
    """Browse-based fake: `folders[folder_id]` is that folder's direct
    children (files and/or subfolders), the same shape `browse_folder`
    returns. The vault root (id 1) is pre-seeded with the three watched
    folders this test file uses, so `_resolve_folder_id` can find each by
    name without every test setting that part up."""

    def __init__(self) -> None:
        self.folders: dict[int, list[PdmObjectInfo]] = {
            ROOT_ID: [
                make_folder(id=MADE_FOLDER_ID, name="Made-Parts", path="\\Made-Parts"),
                make_folder(id=BOUGHT_FOLDER_ID, name="Bought-Parts", path="\\Bought-Parts"),
                make_folder(id=BY_KIND_FOLDER_ID, name="Parts", path="\\Parts"),
            ]
        }
        self.browse_errors: dict[int, Exception] = {}
        self.browse_calls: list[int] = []
        self.by_id: dict[int, PdmObjectInfo] = {}
        self.variables: dict[int, list[PdmConfigVariables]] = {}
        self.variable_errors: dict[int, Exception] = {}
        self.variables_calls: list[int] = []
        self.vault_info_result = PdmVaultInfo(
            vault_id="V1",
            version=1,
            vault_type="SolidWorks",
            archive_server="archive",
            database_name="db",
            database_server="dbserver",
        )
        # Write-back (PdmWriteBack): see WRITE_BACK_VAR_MAP below for the
        # variable names this default card carries.
        self.datacard_result: PdmDataCard | Exception = make_write_back_card()
        self.set_result: bool | Exception = True
        self.datacard_calls: list[int] = []
        self.set_calls: list[tuple[int, dict[str, str]]] = []

    async def browse_folder(self, token: str, folder_id: int) -> list[PdmObjectInfo]:
        self.browse_calls.append(folder_id)
        if folder_id in self.browse_errors:
            raise self.browse_errors[folder_id]
        return self.folders.get(folder_id, [])

    async def files_info(self, token: str, file_ids: list[int]) -> list[PdmObjectInfo]:
        return [self.by_id[i] for i in file_ids if i in self.by_id]

    async def file_variables(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> list[PdmConfigVariables]:
        self.variables_calls.append(file_id)
        if file_id in self.variable_errors:
            raise self.variable_errors[file_id]
        return self.variables.get(file_id, [])

    async def vault_info(self, token: str) -> PdmVaultInfo:
        return self.vault_info_result

    async def get_datacard(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> PdmDataCard:
        self.datacard_calls.append(file_id)
        if isinstance(self.datacard_result, Exception):
            raise self.datacard_result
        return self.datacard_result

    async def set_datacard_variables(
        self,
        token: str,
        file_id: int,
        folder_id: int,
        configuration_id: int,
        card: PdmDataCard,
        values: dict[str, str],
    ) -> bool:
        self.set_calls.append((file_id, dict(values)))
        if isinstance(self.set_result, Exception):
            raise self.set_result
        return self.set_result


class FakeSession:
    def __init__(self, gateway: FakeGateway) -> None:
        self._gateway = gateway

    async def call(self, fn):
        return await fn(self._gateway, "token")


class FakeSnapshotRepository:
    def __init__(self, rows: list[PdmFileSnapshot] | None = None) -> None:
        self._rows: dict[tuple[str, int], PdmFileSnapshot] = {
            (r.vault_id, r.file_id): r for r in (rows or [])
        }
        self._next_id = 100
        self.written_file_ids: list[int] = []

    async def get_by_file(self, vault_id: str, file_id: int) -> PdmFileSnapshot | None:
        return self._rows.get((vault_id, file_id))

    async def upsert_many(self, items: list[PdmFileSnapshot]) -> None:
        for item in items:
            if item.id == 0:
                item.id = self._next_id
                self._next_id += 1
            self._rows[(item.vault_id, item.file_id)] = item
            self.written_file_ids.append(item.file_id)

    async def get_all_for_vault(self, vault_id: str) -> list[PdmFileSnapshot]:
        return [r for (vid, _), r in self._rows.items() if vid == vault_id]

    async def get_by_file_ids(self, vault_id: str, file_ids: list[int]) -> list[PdmFileSnapshot]:
        wanted = set(file_ids)
        return [r for (vid, fid), r in self._rows.items() if vid == vault_id and fid in wanted]

    async def get_by_parent_folder_ids(
        self, vault_id: str, folder_ids: list[int]
    ) -> list[PdmFileSnapshot]:
        wanted = set(folder_ids)
        return [
            r
            for (vid, _), r in self._rows.items()
            if vid == vault_id and r.parent_folder_id in wanted
        ]

    async def list_conflicts(self, vault_id: str) -> list[PdmFileSnapshot]:
        return [
            r
            for r in self._rows.values()
            if r.vault_id == vault_id and r.sync_state == PdmFileSyncState.CONFLICT.value
        ]

    def get(self, vault_id: str, file_id: int) -> PdmFileSnapshot | None:
        return self._rows.get((vault_id, file_id))


class FakeMadeItemRepository:
    def __init__(self, items: list[MadeItem] | None = None) -> None:
        self._items = {i.id: i for i in (items or [])}

    async def get_by_id(self, id: int) -> MadeItem | None:
        return self._items.get(id)

    async def save(self, item: MadeItem) -> MadeItem:
        self._items[item.id] = item
        return item

    async def get_family_by_pdm_file(self, vault_id: str, pdm_file_id: int) -> list[MadeItem]:
        """PdmWriteBack._build_glados_ids' own read; no items are seeded
        for most of this file's tests, an empty family is a perfectly
        valid (if uninteresting) Glados.Ids payload for them."""
        rows = [
            i
            for i in self._items.values()
            if not i.archived and i.vault_id == vault_id and i.pdm_file_id == pdm_file_id
        ]
        rows.sort(key=lambda i: i.revision, reverse=True)
        return rows


class FakeBoughtItemRepository:
    def __init__(self, items: list[BoughtItem] | None = None) -> None:
        self._items = {i.id: i for i in (items or [])}

    async def get_by_id(self, id: int) -> BoughtItem | None:
        return self._items.get(id)

    async def save(self, item: BoughtItem) -> BoughtItem:
        self._items[item.id] = item
        return item

    async def get_by_pdm_file(self, vault_id: str, pdm_file_id: int) -> BoughtItem | None:
        """PdmWriteBack._build_glados_ids' own read, see the made
        repository's sibling method above."""
        return next(
            (
                i
                for i in self._items.values()
                if not i.archived and i.vault_id == vault_id and i.pdm_file_id == pdm_file_id
            ),
            None,
        )


class FakeIngest:
    """Configurable per-file-id outcome/exception, so a poll run can be
    made to exercise several branches (success, skip, conflict, error) in
    one pass without depending on IngestPdmFile's real rule engine."""

    def __init__(
        self,
        *,
        outcomes: dict[int, IngestOutcome] | None = None,
        raises: dict[int, Exception] | None = None,
        default_action: str = "created",
    ) -> None:
        self.calls: list[PdmFilePayload] = []
        self._outcomes = outcomes or {}
        self._raises = raises or {}
        self._default_action = default_action

    async def execute(self, payload: PdmFilePayload) -> IngestOutcome:
        self.calls.append(payload)
        if payload.file_id in self._raises:
            raise self._raises[payload.file_id]
        if payload.file_id in self._outcomes:
            return self._outcomes[payload.file_id]
        return IngestOutcome(action=self._default_action, item_id=payload.file_id, message="ok")


class FakeDocumentSync:
    """Configurable per-file-id outcome/exception for
    PdmDocumentSync.sync_one, mirroring FakeIngest's shape; the poller's
    own documents-folder routing is what this file tests, not
    PdmDocumentSync's own matching/download rules (see
    tests/unit/test_pdm_documents.py for those)."""

    def __init__(
        self,
        *,
        outcomes: dict[int, IngestOutcome] | None = None,
        raises: dict[int, Exception] | None = None,
        default_action: str = "document",
    ) -> None:
        self.calls: list[PdmObjectInfo] = []
        self._outcomes = outcomes or {}
        self._raises = raises or {}
        self._default_action = default_action

    async def sync_one(
        self, *, vault_id: str, folder: PdmWatchedFolder, obj: PdmObjectInfo
    ) -> IngestOutcome:
        self.calls.append(obj)
        if obj.id in self._raises:
            raise self._raises[obj.id]
        if obj.id in self._outcomes:
            return self._outcomes[obj.id]
        return IngestOutcome(action=self._default_action, item_id=obj.id, message="ok")


class FakeThumbnails:
    """Records every call; PdmThumbnails' own behaviour has its dedicated
    coverage in tests/unit/test_pdm_documents.py."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, PdmObjectInfo, str, IngestOutcome]] = []

    async def after_ingest(
        self,
        vault_id: str,
        file: PdmObjectInfo,
        kind: str,
        outcome: IngestOutcome,
        run: PdmSyncRun,
    ) -> str | None:
        self.calls.append((vault_id, file, kind, outcome))
        return None


class FakeSyncRunRepository:
    """In-memory IPdmSyncRunRepository: tracks runs and their entries by
    id, plus which run ids `finish`/`prune` were called with, so a test can
    assert on the recorded trigger, entries and final counts without a
    database."""

    def __init__(self) -> None:
        self.runs: dict[int, PdmSyncRun] = {}
        self.entries: dict[int, list[PdmSyncRunEntry]] = {}
        self.finished_run_ids: list[int] = []
        self.prune_calls: list[timedelta] = []
        self.progress: list[PdmSyncRun] = []
        self._next_run_id = 1
        self._next_entry_id = 1

    async def start(self, run: PdmSyncRun) -> PdmSyncRun:
        run.id = self._next_run_id
        self._next_run_id += 1
        self.runs[run.id] = run
        self.entries[run.id] = []
        return run

    async def finish(self, run: PdmSyncRun) -> None:
        self.runs[run.id] = run
        self.finished_run_ids.append(run.id)

    async def save_progress(self, run: PdmSyncRun) -> None:
        # A copy per write, so a test can follow how the progress moved.
        self.progress.append(dataclasses.replace(run))

    async def add_entries(self, run_id: int, entries: list[PdmSyncRunEntry]) -> None:
        for entry in entries:
            entry.id = self._next_entry_id
            self._next_entry_id += 1
        self.entries.setdefault(run_id, []).extend(entries)

    async def get_multi(self, skip: int | None, limit: int | None) -> tuple[int, list[PdmSyncRun]]:
        rows = sorted(self.runs.values(), key=lambda r: r.started_at, reverse=True)
        return len(rows), rows

    async def get_by_id(self, id: int) -> PdmSyncRun | None:
        return self.runs.get(id)

    async def get_entries(
        self, run_id: int, skip: int | None, limit: int | None, action: str | None
    ) -> tuple[int, list[PdmSyncRunEntry]]:
        rows = self.entries.get(run_id, [])
        if action:
            rows = [e for e in rows if e.action == action]
        return len(rows), rows

    async def prune(self, older_than: datetime) -> int:
        # The retention the cutoff implies, in whole days, so a test can
        # compare it with SYNC_RUN_RETENTION without freezing the clock.
        self.prune_calls.append(timedelta(days=round((now_utc() - older_than) / timedelta(days=1))))
        return 0


class FakeFolderPollStateRepository:
    """In-memory IPdmFolderPollStateRepository: rows keyed by
    (vault_id, folder_key), the same style as this file's other fakes,
    lets a test seed cold state ahead of a run and inspect what the run
    left behind through `get`."""

    def __init__(self, states: list[PdmFolderPollState] | None = None) -> None:
        self._rows: dict[tuple[str, str], PdmFolderPollState] = {
            (s.vault_id, s.folder_key): s for s in (states or [])
        }
        self._next_id = 1000

    async def get_all_for_vault(self, vault_id: str) -> dict[str, PdmFolderPollState]:
        return {key[1]: s for key, s in self._rows.items() if key[0] == vault_id}

    async def upsert(self, state: PdmFolderPollState) -> None:
        if state.id == 0:
            state.id = self._next_id
            self._next_id += 1
        self._rows[(state.vault_id, state.folder_key)] = state

    async def reset(self, vault_id: str, folder_key: str) -> None:
        existing = self._rows.get((vault_id, folder_key))
        if existing is None:
            return
        existing.consecutive_unchanged_runs = 0
        existing.next_due_at = None
        existing.last_changed_at = datetime.now(UTC)

    def get(self, vault_id: str, key: str) -> PdmFolderPollState | None:
        return self._rows.get((vault_id, key))


class Rig:
    def __init__(
        self,
        *,
        settings: AdminPdmSettings | None = None,
        snapshots: list[PdmFileSnapshot] | None = None,
        made_items: list[MadeItem] | None = None,
        bought_items: list[BoughtItem] | None = None,
        ingest: FakeIngest | None = None,
        document_sync: FakeDocumentSync | None = None,
        thumbnails: FakeThumbnails | None = None,
        folder_poll_states: list[PdmFolderPollState] | None = None,
    ) -> None:
        self.gateway = FakeGateway()
        self.session = FakeSession(self.gateway)
        self.admin_settings_repo = FakeAdminSettingsRepository(settings or make_pdm_settings())
        self.snapshot_repo = FakeSnapshotRepository(snapshots)
        self.made_item_repo = FakeMadeItemRepository(made_items)
        self.bought_item_repo = FakeBoughtItemRepository(bought_items)
        self.ingest = ingest or FakeIngest()
        self.document_sync = document_sync or FakeDocumentSync()
        self.thumbnails = thumbnails or FakeThumbnails()
        self.run_repo = FakeSyncRunRepository()
        self.folder_poll_state_repo = FakeFolderPollStateRepository(folder_poll_states)
        self.uow = FakeUnitOfWork()
        # A real PdmWriteBack over the same fakes: inert by default since
        # make_pdm_settings() defaults writeback_enabled=False, so it costs
        # this file nothing unless a test opts in; see
        # tests/unit/test_pdm_writeback.py for its own dedicated coverage.
        self.write_back = PdmWriteBack(
            session=self.session,  # type: ignore[arg-type]
            settings_repo=self.admin_settings_repo,  # type: ignore[arg-type]
            made_repo=self.made_item_repo,  # type: ignore[arg-type]
            bought_repo=self.bought_item_repo,  # type: ignore[arg-type]
            run_repo=self.run_repo,  # type: ignore[arg-type]
        )

        self.use_case = PollPdmVault(
            session=self.session,  # type: ignore[arg-type]
            admin_settings_repo=self.admin_settings_repo,  # type: ignore[arg-type]
            snapshot_repo=self.snapshot_repo,  # type: ignore[arg-type]
            made_item_repo=self.made_item_repo,  # type: ignore[arg-type]
            bought_item_repo=self.bought_item_repo,  # type: ignore[arg-type]
            ingest=self.ingest,  # type: ignore[arg-type]
            write_back=self.write_back,
            document_sync=self.document_sync,  # type: ignore[arg-type]
            thumbnails=self.thumbnails,  # type: ignore[arg-type]
            run_repo=self.run_repo,  # type: ignore[arg-type]
            folder_poll_state_repo=self.folder_poll_state_repo,  # type: ignore[arg-type]
            uow=self.uow,
        )

    def rebuild(self, session: object | None = None) -> None:
        """Rebuilds the use case after swapping in a broken gateway/session
        mid-test, for the top-level-failure tests. `session` replaces the
        default FakeSession, for a test that
        runs the poll through a real PdmSessionService."""
        self.session = session or FakeSession(self.gateway)  # type: ignore[assignment]
        self.write_back = PdmWriteBack(
            session=self.session,  # type: ignore[arg-type]
            settings_repo=self.admin_settings_repo,  # type: ignore[arg-type]
            made_repo=self.made_item_repo,  # type: ignore[arg-type]
            bought_repo=self.bought_item_repo,  # type: ignore[arg-type]
            run_repo=self.run_repo,  # type: ignore[arg-type]
        )
        self.use_case = PollPdmVault(
            session=self.session,  # type: ignore[arg-type]
            admin_settings_repo=self.admin_settings_repo,  # type: ignore[arg-type]
            snapshot_repo=self.snapshot_repo,  # type: ignore[arg-type]
            made_item_repo=self.made_item_repo,  # type: ignore[arg-type]
            bought_item_repo=self.bought_item_repo,  # type: ignore[arg-type]
            ingest=self.ingest,  # type: ignore[arg-type]
            write_back=self.write_back,
            document_sync=self.document_sync,  # type: ignore[arg-type]
            thumbnails=self.thumbnails,  # type: ignore[arg-type]
            run_repo=self.run_repo,  # type: ignore[arg-type]
            folder_poll_state_repo=self.folder_poll_state_repo,  # type: ignore[arg-type]
            uow=self.uow,
        )
