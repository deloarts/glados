"""
Unit tests for RefreshPdmFile: the single-file refresh path used by both
the pdm_sync worker (RequestPdmFileRefresh's trigger) and, later, an admin
retry action. There is no database and no HTTP: IngestPdmFile itself is a fake here
(its own rules are covered by tests/unit/ingest_pdm_file/); these tests only
exercise RefreshPdmFile's own resolution/upsert/error-recording logic.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import ClassVar
from typing import cast

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.external_data.application.dto.pdm_dto import IngestOutcome
from src.modules.external_data.application.dto.pdm_dto import PdmFilePayload
from src.modules.external_data.application.services.pdm_writeback import PdmWriteBack
from src.modules.external_data.application.use_cases.pdm.refresh_pdm_file import RefreshPdmFile
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.entities.pdm_folder_poll_state import PdmFolderPollState
from src.modules.external_data.domain.entities.pdm_sync_run import SYNC_RUN_RETENTION
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRunEntry
from src.modules.external_data.domain.errors import PdmApiError
from src.modules.external_data.domain.services.pdm_poll_cadence import folder_key
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.domain.value_objects.pdm_watched_folder import match_watched_folder
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConfigVariables
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCard
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCardConfiguration
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCardVariable
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmVaultInfo
from src.shared_kernel.domain.services.clock import now_utc
from tests.unit.fakes import FakeUnitOfWork

MADE_FOLDER = PdmWatchedFolder(path="\\Made-Parts", kind="made", recursive=True, enabled=True)
BOUGHT_FOLDER_FLAT = PdmWatchedFolder(
    path="\\Bought-Parts\\Standard", kind="bought", recursive=False, enabled=True
)
BY_KIND_FOLDER = PdmWatchedFolder(path="\\Parts", kind="by_kind", recursive=True, enabled=True)
DOCUMENTS_FOLDER = PdmWatchedFolder(
    path="\\Exported Documents",
    kind="documents",
    recursive=True,
    enabled=True,
    match_by="filename",
    filename_pattern=r"^(?P<part_number>[A-Z0-9-]+)_(?P<revision>[A-Z0-9]+)\.\w+$",
)

# Write-back (PdmWriteBack): the three fields' variable names, used both to
# extend make_pdm_settings()'s variable maps and to build the matching
# FakeGateway.datacard_result default.
WRITE_BACK_VAR_MAP = {
    "glados_ids": "Glados.Ids",
    "newest_revision_sync_state": "Glados.NewestRevisionSyncState",
    "newest_revision_synced_at": "Glados.NewestRevisionSyncedAt",
}


def make_write_back_card() -> PdmDataCard:
    variables = tuple(
        PdmDataCardVariable(
            var_id=i, name=name, value="", var_type=1, version_free=True, read_only=False
        )
        for i, name in enumerate(WRITE_BACK_VAR_MAP.values(), start=1)
    )
    return PdmDataCard(
        configurations=(PdmDataCardConfiguration(id=1, name="@", variables=variables),),
        variables_with_write_all_configs=(),
    )


def make_object(
    *,
    id: int = 100,
    name: str = "part.sldprt",
    path: str = "\\Made-Parts\\part.sldprt",
    version: int = 5,
    state_id: int = 10,
    state: str = "Released",
    parent_folder_id: int = 1,
) -> PdmObjectInfo:
    return PdmObjectInfo(
        id=id,
        name=name,
        size=0,
        modified_at=None,
        version=version,
        state=state,
        state_id=state_id,
        parent_folder_id=parent_folder_id,
        path=path,
        object_type=1,
        is_locked=False,
        locked_by=0,
        is_shared=False,
        is_toolbox=False,
        is_deleted=False,
    )


def make_pdm_settings(**overrides: object) -> AdminPdmSettings:
    defaults: dict[str, object] = dict(
        id=1,
        made_item_variable_map={"part_number": "PDM.PartNumber", "revision": "PDM.Revision"},
        bought_item_variable_map={"part_number": "PDM.PartNumber", "revision": "PDM.Revision"},
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
        watched_folders=[MADE_FOLDER, BOUGHT_FOLDER_FLAT],
        made_released_state_ids=[10],
        made_obsolete_state_ids=[20],
        made_replaced_state_ids=[20],
        bought_released_state_ids=[10],
        bought_obsolete_state_ids=[20],
        bought_replaced_state_ids=[20],
        poll_interval_minutes=15,
        vault_id="V1",
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
    # A stored map always names the kind variable, so one left out of an
    # override is added here.
    made_map = cast(dict[str, str], defaults["made_item_variable_map"])
    defaults["made_item_variable_map"] = {"kind": "Glados.Kind", **made_map}
    return AdminPdmSettings(**defaults)  # type: ignore[arg-type]


class FakeAdminSettingsRepository:
    def __init__(self, pdm: AdminPdmSettings) -> None:
        self._pdm = pdm
        self.saved_vault_id: str | None = None

    async def get_pdm(self) -> AdminPdmSettings:
        return self._pdm

    async def save_pdm_vault_id(self, vault_id: str) -> None:
        self.saved_vault_id = vault_id
        self._pdm.vault_id = vault_id


class FakeGateway:
    def __init__(self) -> None:
        self.by_id: dict[int, PdmObjectInfo] = {}
        self.by_path: dict[str, PdmObjectInfo] = {}
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
        # Write-back (PdmWriteBack): see WRITE_BACK_VAR_MAP above for the
        # variable names this default card carries.
        self.datacard_result: PdmDataCard | Exception = make_write_back_card()
        self.set_result: bool | Exception = True
        self.datacard_calls: list[int] = []
        self.set_calls: list[tuple[int, dict[str, str]]] = []

    async def files_info(self, token: str, file_ids: list[int]) -> list[PdmObjectInfo]:
        return [self.by_id[i] for i in file_ids if i in self.by_id]

    async def file_info_from_path(self, token: str, path: str) -> PdmObjectInfo | None:
        return self.by_path.get(path)

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
        self._next_id = 1

    async def get_by_file(self, vault_id: str, file_id: int) -> PdmFileSnapshot | None:
        return self._rows.get((vault_id, file_id))

    async def upsert_many(self, items: list[PdmFileSnapshot]) -> None:
        for item in items:
            if item.id == 0:
                item.id = self._next_id
                self._next_id += 1
            self._rows[(item.vault_id, item.file_id)] = item

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
        """PdmWriteBack._build_glados_ids' own read. No items are seeded
        for most of this file's tests, so an empty family is a perfectly
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
    def __init__(self, outcome: IngestOutcome | None = None, raises: Exception | None = None):
        self.calls: list[PdmFilePayload] = []
        self._outcome = outcome or IngestOutcome(action="created", item_id=1, message="ok")
        self._raises = raises

    async def execute(self, payload: PdmFilePayload) -> IngestOutcome:
        self.calls.append(payload)
        if self._raises is not None:
            raise self._raises
        return self._outcome


class FakeDocumentSync:
    """PdmDocumentSync.sync_one's own matching/download rules have their
    dedicated coverage in tests/unit/test_pdm_documents.py; this file only
    tests RefreshPdmFile's own routing to it."""

    def __init__(self, outcome: IngestOutcome | None = None, raises: Exception | None = None):
        self.calls: list[PdmObjectInfo] = []
        self._outcome = outcome or IngestOutcome(action="document", item_id=1, message="ok")
        self._raises = raises

    async def sync_one(
        self, *, vault_id: str, folder: PdmWatchedFolder, obj: PdmObjectInfo
    ) -> IngestOutcome:
        self.calls.append(obj)
        if self._raises is not None:
            raise self._raises
        return self._outcome


class FakeThumbnails:
    """PdmThumbnails' own behaviour has its dedicated coverage in
    tests/unit/test_pdm_documents.py."""

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
    """In-memory IPdmSyncRunRepository, the same shape as
    tests/unit/poll_pdm_vault/rig.py's own copy. It tracks runs and entries by
    id so a test can assert on the recorded trigger/entries/final counts
    without a database."""

    def __init__(self) -> None:
        self.runs: dict[int, PdmSyncRun] = {}
        self.entries: dict[int, list[PdmSyncRunEntry]] = {}
        self.finished_run_ids: list[int] = []
        self.prune_calls: list[timedelta] = []
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
    """In-memory IPdmFolderPollStateRepository, the same shape as
    tests/unit/poll_pdm_vault/rig.py's own copy. This file only exercises
    `reset` (the trigger path never advances the unchanged-streak side)."""

    def __init__(self, states: list[PdmFolderPollState] | None = None) -> None:
        self._rows: dict[tuple[str, str], PdmFolderPollState] = {
            (s.vault_id, s.folder_key): s for s in (states or [])
        }

    async def get_all_for_vault(self, vault_id: str) -> dict[str, PdmFolderPollState]:
        return {key[1]: s for key, s in self._rows.items() if key[0] == vault_id}

    async def upsert(self, state: PdmFolderPollState) -> None:
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
        # this file nothing unless a test opts in. See
        # tests/unit/test_pdm_writeback.py for its own dedicated coverage.
        self.write_back = PdmWriteBack(
            session=self.session,  # type: ignore[arg-type]
            settings_repo=self.admin_settings_repo,  # type: ignore[arg-type]
            made_repo=self.made_item_repo,  # type: ignore[arg-type]
            bought_repo=self.bought_item_repo,  # type: ignore[arg-type]
            run_repo=self.run_repo,  # type: ignore[arg-type]
        )

        self.use_case = RefreshPdmFile(
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


class TestWatchedFolderKind:
    def test_recursive_folder_matches_nested_file(self) -> None:
        folder = match_watched_folder([MADE_FOLDER], "\\Made-Parts\\Sub\\part.sldprt")
        assert folder is not None and folder.kind == "made"

    def test_non_recursive_folder_excludes_nested_file(self) -> None:
        folder = match_watched_folder(
            [BOUGHT_FOLDER_FLAT], "\\Bought-Parts\\Standard\\Sub\\bolt.sldprt"
        )
        assert folder is None

    def test_non_recursive_folder_matches_direct_child(self) -> None:
        folder = match_watched_folder([BOUGHT_FOLDER_FLAT], "\\Bought-Parts\\Standard\\bolt.sldprt")
        assert folder is not None and folder.kind == "bought"

    def test_file_outside_every_folder_returns_none(self) -> None:
        folder = match_watched_folder([MADE_FOLDER, BOUGHT_FOLDER_FLAT], "\\Other\\thing.sldprt")
        assert folder is None

    def test_longest_matching_folder_wins(self) -> None:
        broad = PdmWatchedFolder(path="\\Made", kind="made", recursive=True, enabled=True)
        narrow = PdmWatchedFolder(path="\\Made\\Sub", kind="bought", recursive=True, enabled=True)
        folder = match_watched_folder([broad, narrow], "\\Made\\Sub\\part.sldprt")
        assert folder is not None and folder.kind == "bought"

    def test_disabled_folder_is_ignored(self) -> None:
        disabled = PdmWatchedFolder(path="\\Made", kind="made", recursive=True, enabled=False)
        folder = match_watched_folder([disabled], "\\Made\\part.sldprt")
        assert folder is None


class TestRefreshByIdentity:
    async def test_by_file_id(self) -> None:
        rig = Rig()
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(
                configuration_name="@",
                configuration_id=1,
                variables={"PDM.PartNumber": "CAD-1", "PDM.Revision": "A"},
            )
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        assert len(rig.ingest.calls) == 1
        payload = rig.ingest.calls[0]
        assert payload.file_id == 100
        assert payload.kind == "made"
        assert payload.variables["PDM.PartNumber"] == "CAD-1"

    async def test_by_path(self) -> None:
        rig = Rig()
        obj = make_object(id=200, path="\\Made-Parts\\part2.sldprt")
        rig.gateway.by_path["\\Made-Parts\\part2.sldprt"] = obj
        rig.gateway.variables[200] = [
            PdmConfigVariables(configuration_name="@", configuration_id=1, variables={})
        ]

        await rig.use_case.execute(
            vault_name="MyVault", file_id=None, path="\\Made-Parts\\part2.sldprt"
        )

        assert len(rig.ingest.calls) == 1
        assert rig.ingest.calls[0].file_id == 200

    async def test_missing_file_level_configuration_is_skipped_without_ingest(self) -> None:
        # A file with no "@" file-level card to read is skipped rather than
        # falling back to whichever configuration comes first ("Default"
        # here).
        rig = Rig()
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(
                configuration_name="Default", configuration_id=1, variables={"A": "1"}
            )
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        assert rig.ingest.calls == []
        snapshot = rig.snapshot_repo.get("V1", 100)
        assert snapshot is not None
        assert snapshot.sync_state == PdmFileSyncState.SKIPPED.value
        assert snapshot.last_error == "no file-level datacard configuration"


class TestNotFound:
    async def test_not_found_marks_existing_snapshot_missing(self) -> None:
        existing = PdmFileSnapshot(
            id=1,
            vault_id="V1",
            file_id=999,
            kind="made",
            name="gone.sldprt",
            path="\\Made-Parts\\gone.sldprt",
            parent_folder_id=1,
            version=1,
            state_id=10,
            state="Released",
            modified_at=None,
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
            last_ingested_version=1,
            sync_state=PdmFileSyncState.INGESTED,
            last_error=None,
            part_number="CAD-9",
            revision="A",
            item_id=42,
            parked_payload=None,
        )
        made_item = MadeItem(
            id=42,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision="A",
            revision_date=None,
            revision_note=None,
            article_name="Bracket",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.CAD,
            part_number="CAD-9",
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=1,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
            vault_id="V1",
            pdm_file_id=999,
            pdm_file_version=1,
            pdm_synced_at=None,
            pdm_sync_state=None,
            pdm_source_item_id=None,
        )
        rig = Rig(snapshots=[existing], made_items=[made_item])

        await rig.use_case.execute(vault_name="MyVault", file_id=999, path=None)

        updated = rig.snapshot_repo.get("V1", 999)
        assert updated is not None
        assert updated.sync_state == PdmFileSyncState.MISSING.value
        assert (await rig.made_item_repo.get_by_id(42)).pdm_sync_state == PdmSyncState.MISSING.value  # type: ignore[union-attr]
        assert rig.ingest.calls == []

    async def test_not_found_without_existing_snapshot_is_a_noop(self) -> None:
        rig = Rig()

        await rig.use_case.execute(vault_name="MyVault", file_id=12345, path=None)

        assert rig.ingest.calls == []

    async def test_not_found_by_path_alone_is_a_noop(self) -> None:
        rig = Rig()

        await rig.use_case.execute(vault_name="MyVault", file_id=None, path="\\Nowhere\\x.sldprt")

        assert rig.ingest.calls == []


class TestOutsideWatchedFolders:
    async def test_file_outside_every_folder_is_ignored(self) -> None:
        rig = Rig()
        obj = make_object(id=300, path="\\Other\\thing.sldprt")
        rig.gateway.by_id[300] = obj

        await rig.use_case.execute(vault_name="MyVault", file_id=300, path=None)

        assert rig.ingest.calls == []
        assert rig.snapshot_repo.get("V1", 300) is None

    async def test_nested_file_in_non_recursive_folder_is_ignored(self) -> None:
        rig = Rig()
        obj = make_object(id=400, path="\\Bought-Parts\\Standard\\Sub\\bolt.sldprt")
        rig.gateway.by_id[400] = obj

        await rig.use_case.execute(vault_name="MyVault", file_id=400, path=None)

        assert rig.ingest.calls == []


def _make_snapshot(
    *, file_id: int, kind: str | None, item_id: int | None, path: str
) -> PdmFileSnapshot:
    return PdmFileSnapshot(
        id=1,
        vault_id="V1",
        file_id=file_id,
        kind=kind,
        name="part.sldprt",
        path=path,
        parent_folder_id=1,
        version=4,
        state_id=10,
        state="Released",
        modified_at=None,
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        last_ingested_version=4,
        sync_state=PdmFileSyncState.INGESTED,
        last_error=None,
        part_number="CAD-9",
        revision="A",
        item_id=item_id,
        parked_payload=None,
    )


def _make_made_item(*, id: int, file_id: int) -> MadeItem:
    return MadeItem(
        id=id,
        created=datetime.now(UTC),
        changed=datetime.now(UTC),
        changes=[],
        archived=False,
        revision="A",
        revision_date=None,
        revision_note=None,
        article_name="Bracket",
        status=MadeItemCatalogueStatus.ACTIVE,
        data_source=DataSource.CAD,
        part_number="CAD-9",
        material=None,
        mass=None,
        base_size=None,
        note=None,
        weblink=None,
        files=[],
        creator_id=1,
        approver_id=None,
        bought_item_id=None,
        source_item_id=None,
        article_group_ids=[],
        successor_item_id=None,
        changed_by_id=None,
        vault_id="V1",
        pdm_file_id=file_id,
        pdm_file_version=4,
        pdm_synced_at=None,
        pdm_sync_state=None,
        pdm_source_item_id=None,
    )


class TestMovedOutsideWatchedFolder:
    """A file that still resolves in PDM but has moved outside every
    watched folder is, for an already-linked snapshot, the same outcome as
    the file disappearing entirely (_handle_not_found). See
    refresh_pdm_file.py's own docstring."""

    async def test_moved_linked_made_item_is_marked_missing(self) -> None:
        existing = _make_snapshot(
            file_id=900, kind="made", item_id=42, path="\\Made-Parts\\part.sldprt"
        )
        made_item = _make_made_item(id=42, file_id=900)
        rig = Rig(snapshots=[existing], made_items=[made_item])
        obj = make_object(id=900, path="\\Other\\part.sldprt")
        rig.gateway.by_id[900] = obj

        await rig.use_case.execute(vault_name="MyVault", file_id=900, path=None)

        updated = rig.snapshot_repo.get("V1", 900)
        assert updated is not None
        assert updated.sync_state == PdmFileSyncState.MISSING.value
        assert updated.last_error == "file moved outside every watched folder"
        assert (await rig.made_item_repo.get_by_id(42)).pdm_sync_state == PdmSyncState.MISSING.value  # type: ignore[union-attr]
        assert rig.ingest.calls == []

        run = next(iter(rig.run_repo.runs.values()))
        assert run.missing == 1
        entries = rig.run_repo.entries[run.id]
        assert len(entries) == 1
        assert entries[0].action == "missing"
        assert entries[0].file_id == 900
        assert entries[0].message == "file moved outside every watched folder"

    async def test_moved_file_without_a_snapshot_still_yields_skipped(self) -> None:
        rig = Rig()
        obj = make_object(id=901, path="\\Other\\thing.sldprt")
        rig.gateway.by_id[901] = obj

        await rig.use_case.execute(vault_name="MyVault", file_id=901, path=None)

        assert rig.ingest.calls == []
        assert rig.snapshot_repo.get("V1", 901) is None
        run = next(iter(rig.run_repo.runs.values()))
        assert run.skipped == 1
        entries = rig.run_repo.entries[run.id]
        assert len(entries) == 1
        assert entries[0].action == "skipped"
        assert entries[0].message == "file is outside every watched folder"

    async def test_moved_document_snapshot_does_not_touch_the_backing_item(self) -> None:
        # A "document" snapshot's item_id names the made/bought row it
        # backs, not one this snapshot itself owns. See
        # PollPdmVault._sweep_missing's identical guard, mirrored by
        # RefreshPdmFile._mark_missing. The snapshot still goes missing,
        # the item it backs is left untouched.
        existing = _make_snapshot(
            file_id=902,
            kind="document",
            item_id=42,
            path="\\Exported Documents\\CAD-9_A.pdf",
        )
        made_item = _make_made_item(id=42, file_id=902)
        rig = Rig(snapshots=[existing], made_items=[made_item])
        obj = make_object(id=902, path="\\Other\\CAD-9_A.pdf")
        rig.gateway.by_id[902] = obj

        await rig.use_case.execute(vault_name="MyVault", file_id=902, path=None)

        updated = rig.snapshot_repo.get("V1", 902)
        assert updated is not None
        assert updated.sync_state == PdmFileSyncState.MISSING.value
        assert (await rig.made_item_repo.get_by_id(42)).pdm_sync_state is None  # type: ignore[union-attr]


class TestFileTypeRule:
    """The file-type rule applies to a single-file refresh exactly as it
    does to the poller's own walk. See PollPdmVault's own coverage in
    tests/unit/poll_pdm_vault/test_by_kind_and_conflicts.py::TestFileTypeRule
    for the full set of scenarios; this only proves RefreshPdmFile applies
    the same rule."""

    async def test_explicit_folder_non_admitted_extension_is_never_snapshotted(self) -> None:
        rig = Rig()
        obj = make_object(id=500, name="part.sldasm", path="\\Made-Parts\\part.sldasm")
        rig.gateway.by_id[500] = obj

        await rig.use_case.execute(vault_name="MyVault", file_id=500, path=None)

        assert rig.ingest.calls == []
        assert rig.snapshot_repo.get("V1", 500) is None

    async def test_by_kind_folder_rechecks_the_resolved_kinds_own_extensions(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[BY_KIND_FOLDER]))
        obj = make_object(id=600, name="assembly.sldasm", path="\\Parts\\assembly.sldasm")
        rig.gateway.by_id[600] = obj
        rig.gateway.variables[600] = [
            PdmConfigVariables(
                configuration_name="@", configuration_id=1, variables={"Glados.Kind": "made"}
            )
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=600, path=None)

        assert rig.ingest.calls == []
        row = rig.snapshot_repo.get("V1", 600)
        assert row is not None
        assert row.last_error == "sldasm files are not made items"


class TestDocumentsFolder:
    """A `documents` watched folder's file never reaches IngestPdmFile;
    see PollPdmVault's own coverage for the shared matching/download
    rules; this only proves RefreshPdmFile routes to the same service."""

    async def test_routes_to_document_sync(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[DOCUMENTS_FOLDER]))
        obj = make_object(id=700, name="CAD-1_A.pdf", path="\\Exported Documents\\CAD-1_A.pdf")
        rig.gateway.by_id[700] = obj

        await rig.use_case.execute(vault_name="MyVault", file_id=700, path=None)

        assert rig.ingest.calls == []
        assert len(rig.document_sync.calls) == 1
        assert rig.document_sync.calls[0].id == 700
        row = rig.snapshot_repo.get("V1", 700)
        assert row is not None
        assert row.kind == "document"


class TestByKindFolder:
    """A `by_kind` folder (docs/FIELD_OWNERSHIP.md, principle 1) never
    asserts its own kind, it is read from the file's `Glados.Kind`
    (default) datacard variable once the variables are fetched."""

    async def test_resolves_made_from_kind_variable(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[BY_KIND_FOLDER]))
        obj = make_object(id=100, path="\\Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(
                configuration_name="@",
                configuration_id=1,
                variables={"PDM.PartNumber": "CAD-1", "PDM.Revision": "A", "Glados.Kind": "made"},
            )
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        assert len(rig.ingest.calls) == 1
        assert rig.ingest.calls[0].kind == "made"

    async def test_resolves_bought_from_kind_variable(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[BY_KIND_FOLDER]))
        obj = make_object(id=100, path="\\Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(
                configuration_name="@",
                configuration_id=1,
                variables={
                    "PDM.PartNumber": "CAD-1",
                    "PDM.Revision": "A",
                    "Glados.Kind": "bought",
                },
            )
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        assert len(rig.ingest.calls) == 1
        assert rig.ingest.calls[0].kind == "bought"

    async def test_empty_kind_variable_is_skipped_without_ingest(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[BY_KIND_FOLDER]))
        obj = make_object(id=100, path="\\Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(
                configuration_name="@", configuration_id=1, variables={"Glados.Kind": ""}
            )
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        assert rig.ingest.calls == []
        snapshot = rig.snapshot_repo.get("V1", 100)
        assert snapshot is not None
        assert snapshot.kind is None
        assert snapshot.sync_state == PdmFileSyncState.SKIPPED.value
        assert snapshot.last_error == "kind not set"
        run = next(iter(rig.run_repo.runs.values()))
        assert run.skipped == 1

    async def test_missing_kind_variable_is_skipped(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[BY_KIND_FOLDER]))
        obj = make_object(id=100, path="\\Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(configuration_name="@", configuration_id=1, variables={})
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        assert rig.ingest.calls == []
        snapshot = rig.snapshot_repo.get("V1", 100)
        assert snapshot is not None
        assert snapshot.last_error == "kind not set"

    async def test_unknown_kind_value_is_skipped_with_value_in_message(self) -> None:
        rig = Rig(settings=make_pdm_settings(watched_folders=[BY_KIND_FOLDER]))
        obj = make_object(id=100, path="\\Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(
                configuration_name="@", configuration_id=1, variables={"Glados.Kind": "weldment"}
            )
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        assert rig.ingest.calls == []
        snapshot = rig.snapshot_repo.get("V1", 100)
        assert snapshot is not None
        assert snapshot.last_error is not None
        assert "weldment" in snapshot.last_error


class TestExplicitFolderKindDisagreement:
    """The SolidWorks add-in is the first guard against a kind variable
    disagreeing with an explicit made/bought folder; this is the refresh
    path's own backstop (docs/FIELD_OWNERSHIP.md, principle 1)."""

    async def test_disagreeing_variable_is_a_conflict_without_ingest(self) -> None:
        rig = Rig()  # default watched_folders = [MADE_FOLDER, BOUGHT_FOLDER_FLAT]
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(
                configuration_name="@", configuration_id=1, variables={"Glados.Kind": "bought"}
            )
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        assert rig.ingest.calls == []
        snapshot = rig.snapshot_repo.get("V1", 100)
        assert snapshot is not None
        assert snapshot.sync_state == PdmFileSyncState.CONFLICT.value
        assert snapshot.last_error == "kind variable says bought, folder says made"
        run = next(iter(rig.run_repo.runs.values()))
        assert run.conflicts == 1

    async def test_agreeing_variable_proceeds_normally(self) -> None:
        rig = Rig()
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(
                configuration_name="@", configuration_id=1, variables={"Glados.Kind": "made"}
            )
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        assert len(rig.ingest.calls) == 1
        assert rig.ingest.calls[0].kind == "made"

    async def test_blank_variable_does_not_conflict(self) -> None:
        rig = Rig()
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(
                configuration_name="@", configuration_id=1, variables={"Glados.Kind": ""}
            )
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        assert len(rig.ingest.calls) == 1
        assert rig.ingest.calls[0].kind == "made"


class TestErrorRecording:
    async def test_ingest_error_is_recorded_on_the_snapshot(self) -> None:
        rig = Rig(ingest=FakeIngest(raises=RuntimeError("boom")))
        obj = make_object(id=500, path="\\Made-Parts\\bad.sldprt")
        rig.gateway.by_id[500] = obj

        await rig.use_case.execute(vault_name="MyVault", file_id=500, path=None)

        snapshot = rig.snapshot_repo.get("V1", 500)
        assert snapshot is not None
        assert snapshot.sync_state == PdmFileSyncState.ERROR.value
        assert "boom" in (snapshot.last_error or "")

    async def test_ingest_error_rolls_back_before_recording(self) -> None:
        """A failed attempt's pending writes must not be committed along
        with the error record."""
        rig = Rig(ingest=FakeIngest(raises=RuntimeError("boom")))
        rig.gateway.by_id[500] = make_object(id=500, path="\\Made-Parts\\bad.sldprt")

        await rig.use_case.execute(vault_name="MyVault", file_id=500, path=None)

        assert rig.uow.rollbacks >= 1


class TestUnreadableFiles:
    """403 on file_variables (or an empty-state listing that never gets that
    far) is an expected, transient condition, not a failure. See
    docs/OPERATIONS.md section 8."""

    async def test_403_on_variables_is_recorded_as_skipped(self) -> None:
        rig = Rig()
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variable_errors[100] = PdmApiError(
            "PDM call failed with HTTP 403.", status_code=403, body=""
        )

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        assert rig.ingest.calls == []
        snapshot = rig.snapshot_repo.get("V1", 100)
        assert snapshot is not None
        assert snapshot.sync_state == PdmFileSyncState.SKIPPED.value
        assert snapshot.last_error is not None
        assert "not readable" in snapshot.last_error

        run = next(iter(rig.run_repo.runs.values()))
        assert run.skipped == 1
        assert run.errors == 0
        assert run.changed == 1
        entries = rig.run_repo.entries[run.id]
        assert len(entries) == 1
        assert entries[0].action == "skipped"
        assert entries[0].file_id == 100
        assert "not readable" in entries[0].message

    async def test_empty_state_listing_is_skipped_without_calling_variables(self) -> None:
        rig = Rig()
        obj = make_object(id=101, path="\\Made-Parts\\part.sldprt", state="", state_id=0)
        rig.gateway.by_id[101] = obj

        await rig.use_case.execute(vault_name="MyVault", file_id=101, path=None)

        assert rig.gateway.variables_calls == []
        assert rig.ingest.calls == []
        snapshot = rig.snapshot_repo.get("V1", 101)
        assert snapshot is not None
        assert snapshot.sync_state == PdmFileSyncState.SKIPPED.value
        assert snapshot.last_error is not None
        assert "not readable" in snapshot.last_error

        run = next(iter(rig.run_repo.runs.values()))
        assert run.skipped == 1

    async def test_500_on_variables_stays_an_error(self) -> None:
        rig = Rig()
        obj = make_object(id=102, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[102] = obj
        rig.gateway.variable_errors[102] = PdmApiError(
            "PDM call failed with HTTP 500.", status_code=500, body=""
        )

        await rig.use_case.execute(vault_name="MyVault", file_id=102, path=None)

        snapshot = rig.snapshot_repo.get("V1", 102)
        assert snapshot is not None
        assert snapshot.sync_state == PdmFileSyncState.ERROR.value
        assert snapshot.last_error is not None

        run = next(iter(rig.run_repo.runs.values()))
        assert run.errors == 1
        assert run.skipped == 0


class TestSyncRunLog:
    async def test_success_records_a_one_entry_run_with_the_default_trigger(self) -> None:
        rig = Rig()
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(configuration_name="@", configuration_id=1, variables={})
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        assert len(rig.run_repo.runs) == 1
        run = next(iter(rig.run_repo.runs.values()))
        assert run.trigger == PdmSyncTrigger.FILE_TRIGGER.value
        assert run.finished_at is not None
        assert run.files_seen == 1
        assert run.changed == 1
        assert run.ingested == 1
        entries = rig.run_repo.entries[run.id]
        assert len(entries) == 1
        assert entries[0].file_id == 100
        assert entries[0].action == "created"
        assert rig.run_repo.finished_run_ids == [run.id]
        assert rig.run_repo.prune_calls == [SYNC_RUN_RETENTION]

    async def test_explicit_retry_trigger_is_recorded(self) -> None:
        rig = Rig()
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(configuration_name="@", configuration_id=1, variables={})
        ]

        await rig.use_case.execute(
            vault_name="MyVault", file_id=100, path=None, trigger=PdmSyncTrigger.RETRY
        )

        run = next(iter(rig.run_repo.runs.values()))
        assert run.trigger == PdmSyncTrigger.RETRY.value

    async def test_the_requests_reason_and_requester_are_recorded_on_the_run(self) -> None:
        rig = Rig()
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(configuration_name="@", configuration_id=1, variables={})
        ]

        await rig.use_case.execute(
            vault_name="MyVault",
            file_id=100,
            path=None,
            change_reason="state_change",
            change_state="Released",
            requested_by_name="Ada Lovelace",
        )

        run = next(iter(rig.run_repo.runs.values()))
        assert run.change_reason == "state_change"
        assert run.change_state == "Released"
        assert run.requested_by_name == "Ada Lovelace"

    async def test_a_vanished_file_still_records_the_requests_reason(self) -> None:
        rig = Rig()

        await rig.use_case.execute(
            vault_name="MyVault",
            file_id=404,
            path=None,
            change_reason="delete",
            requested_by_name="Ada Lovelace",
        )

        run = next(iter(rig.run_repo.runs.values()))
        assert rig.run_repo.entries[run.id][0].action == "missing"
        assert run.change_reason == "delete"
        assert run.change_state is None
        assert run.requested_by_name == "Ada Lovelace"

    async def test_conflict_outcome_is_tallied_as_a_conflict(self) -> None:
        rig = Rig(
            ingest=FakeIngest(outcome=IngestOutcome(action="conflict", item_id=None, message="x"))
        )
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(configuration_name="@", configuration_id=1, variables={})
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        run = next(iter(rig.run_repo.runs.values()))
        assert run.conflicts == 1
        assert run.ingested == 0

    async def test_outside_watched_folder_records_a_skipped_run(self) -> None:
        rig = Rig()
        obj = make_object(id=300, path="\\Other\\thing.sldprt")
        rig.gateway.by_id[300] = obj

        await rig.use_case.execute(vault_name="MyVault", file_id=300, path=None)

        run = next(iter(rig.run_repo.runs.values()))
        assert run.skipped == 1
        entries = rig.run_repo.entries[run.id]
        assert len(entries) == 1
        assert entries[0].action == "skipped"
        assert entries[0].kind is None
        assert rig.run_repo.prune_calls == [SYNC_RUN_RETENTION]

    async def test_ingest_error_records_an_error_entry(self) -> None:
        rig = Rig(ingest=FakeIngest(raises=RuntimeError("boom")))
        obj = make_object(id=500, path="\\Made-Parts\\bad.sldprt")
        rig.gateway.by_id[500] = obj

        await rig.use_case.execute(vault_name="MyVault", file_id=500, path=None)

        run = next(iter(rig.run_repo.runs.values()))
        assert run.changed == 1
        assert run.errors == 1
        entries = rig.run_repo.entries[run.id]
        assert len(entries) == 1
        assert entries[0].action == "error"
        assert "boom" in entries[0].message

    async def test_not_found_with_existing_snapshot_records_a_missing_run(self) -> None:
        existing = PdmFileSnapshot(
            id=1,
            vault_id="V1",
            file_id=999,
            kind="made",
            name="gone.sldprt",
            path="\\Made-Parts\\gone.sldprt",
            parent_folder_id=1,
            version=1,
            state_id=10,
            state="Released",
            modified_at=None,
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
            last_ingested_version=1,
            sync_state=PdmFileSyncState.INGESTED,
            last_error=None,
            part_number="CAD-9",
            revision="A",
            item_id=None,
            parked_payload=None,
        )
        rig = Rig(snapshots=[existing])

        await rig.use_case.execute(vault_name="MyVault", file_id=999, path=None)

        assert len(rig.run_repo.runs) == 1
        run = next(iter(rig.run_repo.runs.values()))
        assert run.missing == 1
        entries = rig.run_repo.entries[run.id]
        assert len(entries) == 1
        assert entries[0].file_id == 999
        assert entries[0].action == "missing"
        assert entries[0].path == "\\Made-Parts\\gone.sldprt"
        assert rig.run_repo.finished_run_ids == [run.id]
        assert rig.run_repo.prune_calls == [SYNC_RUN_RETENTION]

    async def test_not_found_with_a_known_file_id_but_no_snapshot_still_records_a_run(self) -> None:
        rig = Rig()

        await rig.use_case.execute(vault_name="MyVault", file_id=12345, path=None)

        assert len(rig.run_repo.runs) == 1
        run = next(iter(rig.run_repo.runs.values()))
        assert run.missing == 1
        entries = rig.run_repo.entries[run.id]
        assert entries[0].file_id == 12345
        assert entries[0].name == ""

    async def test_not_found_by_path_alone_records_nothing(self) -> None:
        rig = Rig()

        await rig.use_case.execute(vault_name="MyVault", file_id=None, path="\\Nowhere\\x.sldprt")

        assert rig.run_repo.runs == {}
        assert rig.run_repo.prune_calls == []


class TestWriteBack:
    """PdmWriteBack.after_outcome is wired into execute() after a normal
    ingest and into the private-state skip path when the file is already
    linked. See refresh_pdm_file.py's own module docstring. Full coverage
    of PdmWriteBack's own rules lives in test_pdm_writeback.py; these
    tests only prove the wiring."""

    _WRITE_BACK_MADE_MAP: ClassVar[dict[str, str]] = {
        "part_number": "PDM.PartNumber",
        "revision": "PDM.Revision",
        **WRITE_BACK_VAR_MAP,
    }

    async def test_successful_ingest_triggers_write_back(self) -> None:
        settings = make_pdm_settings(
            writeback_enabled=True, made_item_variable_map=self._WRITE_BACK_MADE_MAP
        )
        rig = Rig(settings=settings)
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(
                configuration_name="@",
                configuration_id=1,
                variables={"PDM.PartNumber": "CAD-1", "PDM.Revision": "A"},
            )
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        assert rig.gateway.datacard_calls == [100]
        assert len(rig.gateway.set_calls) == 1
        file_id, values = rig.gateway.set_calls[0]
        assert file_id == 100
        assert values["Glados.NewestRevisionSyncState"] == "synced"

    async def test_disabled_by_default_never_calls_the_gateway(self) -> None:
        rig = Rig()  # make_pdm_settings() defaults writeback_enabled=False
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(configuration_name="@", configuration_id=1, variables={})
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        assert rig.gateway.datacard_calls == []

    async def test_unlinked_skip_does_not_trigger_write_back(self) -> None:
        settings = make_pdm_settings(
            writeback_enabled=True, made_item_variable_map=self._WRITE_BACK_MADE_MAP
        )
        ingest = FakeIngest(
            outcome=IngestOutcome(action="skipped", item_id=None, message="identity vars missing")
        )
        rig = Rig(settings=settings, ingest=ingest)
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(
                configuration_name="@",
                configuration_id=1,
                variables={"PDM.PartNumber": "CAD-1", "PDM.Revision": "A"},
            )
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        assert rig.gateway.datacard_calls == []

    async def test_conflict_outcome_on_a_linked_item_triggers_write_back(self) -> None:
        settings = make_pdm_settings(
            writeback_enabled=True, made_item_variable_map=self._WRITE_BACK_MADE_MAP
        )
        ingest = FakeIngest(
            outcome=IngestOutcome(action="conflict", item_id=1, message="manufacturer unresolved")
        )
        rig = Rig(settings=settings, ingest=ingest)
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(
                configuration_name="@",
                configuration_id=1,
                variables={"PDM.PartNumber": "CAD-1", "PDM.Revision": "A"},
            )
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        assert len(rig.gateway.set_calls) == 1
        _, values = rig.gateway.set_calls[0]
        assert values["Glados.NewestRevisionSyncState"] == "conflict: manufacturer unresolved"

    async def test_private_state_skip_of_a_linked_file_triggers_write_back(self) -> None:
        existing = PdmFileSnapshot(
            id=1,
            vault_id="V1",
            file_id=101,
            kind="made",
            name="part.sldprt",
            path="\\Made-Parts\\part.sldprt",
            parent_folder_id=1,
            version=4,
            state_id=10,
            state="Released",
            modified_at=None,
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
            last_ingested_version=4,
            sync_state=PdmFileSyncState.INGESTED,
            last_error=None,
            part_number="CAD-1",
            revision="A",
            item_id=42,
            parked_payload=None,
        )
        settings = make_pdm_settings(
            writeback_enabled=True, made_item_variable_map=self._WRITE_BACK_MADE_MAP
        )
        rig = Rig(settings=settings, snapshots=[existing])
        obj = make_object(id=101, path="\\Made-Parts\\part.sldprt", state="", state_id=0)
        rig.gateway.by_id[101] = obj

        await rig.use_case.execute(vault_name="MyVault", file_id=101, path=None)

        assert rig.gateway.datacard_calls == [101]
        assert len(rig.gateway.set_calls) == 1

    async def test_private_state_skip_of_an_unlinked_file_does_not_trigger_write_back(self) -> None:
        settings = make_pdm_settings(
            writeback_enabled=True, made_item_variable_map=self._WRITE_BACK_MADE_MAP
        )
        rig = Rig(settings=settings)
        obj = make_object(id=101, path="\\Made-Parts\\part.sldprt", state="", state_id=0)
        rig.gateway.by_id[101] = obj

        await rig.use_case.execute(vault_name="MyVault", file_id=101, path=None)

        assert rig.gateway.datacard_calls == []


class TestColdFolderCadenceReset:
    """RefreshPdmFile resets the matched folder's cold-folder poll cadence
    state (domain.services.pdm_poll_cadence) after a successful ingest or
    document sync, never after a skip/conflict/error. See this module's
    own docstring."""

    def _stale_state(self, folder: PdmWatchedFolder = MADE_FOLDER) -> PdmFolderPollState:
        return PdmFolderPollState(
            id=1,
            vault_id="V1",
            folder_key=folder_key(folder),
            consecutive_unchanged_runs=3,
            next_due_at=datetime.now(UTC) + timedelta(hours=1),
            last_changed_at=None,
            updated_at=datetime.now(UTC),
        )

    async def test_successful_ingest_resets_the_folder_state(self) -> None:
        rig = Rig(folder_poll_states=[self._stale_state()])
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(configuration_name="@", configuration_id=1, variables={})
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        state = rig.folder_poll_state_repo.get("V1", folder_key(MADE_FOLDER))
        assert state is not None
        assert state.consecutive_unchanged_runs == 0
        assert state.next_due_at is None

    async def test_skipped_outcome_does_not_reset_the_folder_state(self) -> None:
        stale = self._stale_state()
        rig = Rig(
            folder_poll_states=[stale],
            ingest=FakeIngest(outcome=IngestOutcome(action="skipped", item_id=None, message="x")),
        )
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(configuration_name="@", configuration_id=1, variables={})
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        state = rig.folder_poll_state_repo.get("V1", folder_key(MADE_FOLDER))
        assert state is not None
        assert state.consecutive_unchanged_runs == 3
        assert state.next_due_at is not None

    async def test_conflict_outcome_does_not_reset_the_folder_state(self) -> None:
        stale = self._stale_state()
        rig = Rig(
            folder_poll_states=[stale],
            ingest=FakeIngest(outcome=IngestOutcome(action="conflict", item_id=1, message="x")),
        )
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(configuration_name="@", configuration_id=1, variables={})
        ]

        await rig.use_case.execute(vault_name="MyVault", file_id=100, path=None)

        state = rig.folder_poll_state_repo.get("V1", folder_key(MADE_FOLDER))
        assert state is not None
        assert state.consecutive_unchanged_runs == 3
        assert state.next_due_at is not None

    async def test_documents_folder_successful_sync_resets_the_folder_state(self) -> None:
        stale = self._stale_state(folder=DOCUMENTS_FOLDER)
        rig = Rig(
            settings=make_pdm_settings(watched_folders=[DOCUMENTS_FOLDER]),
            folder_poll_states=[stale],
        )
        obj = make_object(id=700, name="CAD-1_A.pdf", path="\\Exported Documents\\CAD-1_A.pdf")
        rig.gateway.by_id[700] = obj

        await rig.use_case.execute(vault_name="MyVault", file_id=700, path=None)

        state = rig.folder_poll_state_repo.get("V1", folder_key(DOCUMENTS_FOLDER))
        assert state is not None
        assert state.consecutive_unchanged_runs == 0
        assert state.next_due_at is None


class TestNoPendingWritesAtPdmRequests:
    """Every PDM request goes through PdmSessionService.call, which commits
    the shared session first (and a token refresh commits it too), so the
    refresh must never reach `call` with writes still staged."""

    class _Tracker:
        def __init__(self) -> None:
            self.pending = False

        async def commit(self) -> None:
            self.pending = False

        async def rollback(self) -> None:
            self.pending = False

    class _CheckingSession:
        def __init__(
            self, gateway: FakeGateway, tracker: "TestNoPendingWritesAtPdmRequests._Tracker"
        ) -> None:
            self._gateway = gateway
            self._tracker = tracker
            self.pending_at_call: list[bool] = []

        async def call(self, fn):
            self.pending_at_call.append(self._tracker.pending)
            return await fn(self._gateway, "token")

    class _CallingThumbnails:
        def __init__(self, session: "TestNoPendingWritesAtPdmRequests._CheckingSession") -> None:
            self._session = session

        async def after_ingest(
            self,
            vault_id: str,
            file: PdmObjectInfo,
            kind: str,
            outcome: IngestOutcome,
            run: PdmSyncRun,
        ) -> str | None:
            async def _do(gw: FakeGateway, token: str) -> list[PdmObjectInfo]:
                return await gw.files_info(token, [file.id])

            await self._session.call(_do)
            return None

    async def test_ingest_with_cadence_reset_write_back_and_thumbnail(self) -> None:
        settings = make_pdm_settings(
            writeback_enabled=True,
            made_item_variable_map={
                "part_number": "PDM.PartNumber",
                "revision": "PDM.Revision",
                **WRITE_BACK_VAR_MAP,
            },
        )
        stale = PdmFolderPollState(
            id=1,
            vault_id="V1",
            folder_key=folder_key(MADE_FOLDER),
            consecutive_unchanged_runs=3,
            next_due_at=datetime.now(UTC) + timedelta(hours=1),
            last_changed_at=None,
            updated_at=datetime.now(UTC),
        )
        rig = Rig(settings=settings, folder_poll_states=[stale])
        obj = make_object(id=100, path="\\Made-Parts\\part.sldprt")
        rig.gateway.by_id[100] = obj
        rig.gateway.variables[100] = [
            PdmConfigVariables(
                configuration_name="@",
                configuration_id=1,
                variables={"PDM.PartNumber": "CAD-1", "PDM.Revision": "A"},
            )
        ]

        tracker = self._Tracker()
        for repo, method in (
            (rig.run_repo, "add_entries"),
            (rig.snapshot_repo, "upsert_many"),
            (rig.folder_poll_state_repo, "reset"),
        ):
            original = getattr(repo, method)

            def make(fn):
                async def wrapper(*args, **kwargs):
                    result = await fn(*args, **kwargs)
                    tracker.pending = True
                    return result

                return wrapper

            setattr(repo, method, make(original))

        session = self._CheckingSession(rig.gateway, tracker)
        write_back = PdmWriteBack(
            session=session,  # type: ignore[arg-type]
            settings_repo=rig.admin_settings_repo,  # type: ignore[arg-type]
            made_repo=rig.made_item_repo,  # type: ignore[arg-type]
            bought_repo=rig.bought_item_repo,  # type: ignore[arg-type]
            run_repo=rig.run_repo,  # type: ignore[arg-type]
        )
        use_case = RefreshPdmFile(
            session=session,  # type: ignore[arg-type]
            admin_settings_repo=rig.admin_settings_repo,  # type: ignore[arg-type]
            snapshot_repo=rig.snapshot_repo,  # type: ignore[arg-type]
            made_item_repo=rig.made_item_repo,  # type: ignore[arg-type]
            bought_item_repo=rig.bought_item_repo,  # type: ignore[arg-type]
            ingest=rig.ingest,  # type: ignore[arg-type]
            write_back=write_back,
            document_sync=rig.document_sync,  # type: ignore[arg-type]
            thumbnails=self._CallingThumbnails(session),  # type: ignore[arg-type]
            run_repo=rig.run_repo,  # type: ignore[arg-type]
            folder_poll_state_repo=rig.folder_poll_state_repo,  # type: ignore[arg-type]
            uow=tracker,  # type: ignore[arg-type]
        )

        await use_case.execute(vault_name="MyVault", file_id=100, path=None)

        # Lookup, variables, datacard, set, thumbnail.
        assert len(session.pending_at_call) == 5
        assert session.pending_at_call == [False] * 5
        state = rig.folder_poll_state_repo.get("V1", folder_key(MADE_FOLDER))
        assert state is not None
        assert state.next_due_at is None
