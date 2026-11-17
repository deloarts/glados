"""
Unit tests for application.use_cases.pdm.pdm_documents: PdmDocumentSync (a
`documents` watched folder's identity matching, category resolution,
download/store, and link bookkeeping) and PdmThumbnails (a made/bought
file's own PDM thumbnail, fetched after a synced ingest). No database, no
HTTP: the gateway is a configurable fake, and the item-file upload path
uses the real UploadMadeItemFile/UploadBoughtItemFile use cases over fake
repositories/storage, so a document ends up going through the exact same
singleton-replace logic a web upload would.
"""

import dataclasses
import io
from datetime import UTC
from datetime import datetime

import pytest
from PIL import Image

from src.modules.catalogue.application.services.item_picture_store import ItemPictureStore
from src.modules.catalogue.application.use_cases.bought_item.upload_bought_item_file import (
    UploadBoughtItemFile,
)
from src.modules.catalogue.application.use_cases.made_item.upload_made_item_file import (
    UploadMadeItemFile,
)
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.bought_item_file import BoughtItemFile
from src.modules.catalogue.domain.entities.item_picture import ItemPicture
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_file import MadeItemFile
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.external_data.application.dto.pdm_dto import IngestOutcome
from src.modules.external_data.application.services.pdm_skip_reasons import is_deliberate_skip
from src.modules.external_data.application.use_cases.pdm.pdm_documents import PdmDocumentSync
from src.modules.external_data.application.use_cases.pdm.pdm_documents import PdmThumbnails
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_document_link import PdmDocumentLink
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.errors import PdmApiError
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConfigVariables
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmFileContent
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo
from src.modules.platform.domain.entities.user import User
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.item_picture_fakes import FakeItemPictureRepository
from tests.unit.item_picture_fakes import FakePictureStorage
from tests.unit.item_picture_fakes import make_picture

MADE_VAR_MAP = {
    "part_number": "PDM.PartNumber",
    "revision": "PDM.Revision",
    "kind": "Glados.Kind",
}
BOUGHT_VAR_MAP = {
    "part_number": "PDM.BoughtPartNumber",
    "kind": "Glados.Kind",
}
DOCUMENT_CATEGORIES = {"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"}

DOCUMENTS_FOLDER_DATACARD = PdmWatchedFolder(
    path="\\Exported Documents",
    kind="documents",
    recursive=True,
    enabled=True,
    match_by="datacard",
)
DOCUMENTS_FOLDER_FILENAME = PdmWatchedFolder(
    path="\\Exported Documents",
    kind="documents",
    recursive=True,
    enabled=True,
    match_by="filename",
    filename_pattern=r"^(?P<part_number>[A-Z0-9-]+)_(?P<revision>[A-Z0-9]+)"
    r"(?:_(?P<kind>made|bought))?\.\w+$",
)


def _jpeg_bytes(size: int = 4) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (size, size), (200, 30, 30)).save(buffer, format="JPEG")
    return buffer.getvalue()


def make_object(
    *,
    id: int = 1,
    name: str = "CAD-1_A.pdf",
    path: str = "\\Exported Documents\\CAD-1_A.pdf",
    version: int = 3,
    parent_folder_id: int = 5,
) -> PdmObjectInfo:
    return PdmObjectInfo(
        id=id,
        name=name,
        size=0,
        modified_at=None,
        version=version,
        state="Released",
        state_id=10,
        parent_folder_id=parent_folder_id,
        path=path,
        object_type=1,
        is_locked=False,
        locked_by=0,
        is_shared=False,
        is_toolbox=False,
        is_deleted=False,
    )


def make_made_item(id: int = 1, *, part_number: str = "CAD-1", revision: str = "A") -> MadeItem:
    return MadeItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        revision=revision,
        revision_date=None,
        revision_note=None,
        article_name="Bracket",
        status=MadeItemCatalogueStatus.ACTIVE,
        data_source=DataSource.CAD,
        part_number=part_number,
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
        pdm_file_id=99,
        pdm_file_version=1,
        pdm_synced_at=None,
        pdm_sync_state=PdmSyncState.SYNCED,
        pdm_source_item_id=None,
    )


def make_bought_item(id: int = 2, *, part_number: str = "CAD-2") -> BoughtItem:
    return BoughtItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        article_name="Bolt",
        order_code_1="OC-1",
        order_code_2=None,
        gtin=None,
        ean=None,
        tariff_number=None,
        status=BoughtItemCatalogueStatus.ACTIVE,
        data_source=DataSource.CAD,
        part_number=part_number,
        mass=None,
        note=None,
        weblink=None,
        files=[],
        creator_id=1,
        approver_id=None,
        manufacturer_id=1,
        article_group_ids=[],
        successor_item_id=None,
        revision=None,
        vault_id="V1",
        pdm_file_id=100,
        pdm_file_version=1,
        pdm_synced_at=None,
        pdm_sync_state=PdmSyncState.SYNCED,
    )


def make_system_user() -> User:
    return make_user(username="system", full_name="System", is_systemuser=True)


def make_pdm_settings(**overrides: object) -> AdminPdmSettings:
    defaults: dict[str, object] = dict(
        id=1,
        made_item_variable_map=dict(MADE_VAR_MAP),
        bought_item_variable_map=dict(BOUGHT_VAR_MAP),
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
        watched_folders=[DOCUMENTS_FOLDER_DATACARD],
        made_released_state_ids=[10],
        document_released_state_ids=[10],
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
        document_categories=dict(DOCUMENT_CATEGORIES),
        thumbnails_enabled=True,
        stuck_after_days=7,
        reconcile_requested_deep=None,
        required_fields={"made": [], "bought": []},
    )
    defaults.update(overrides)
    return AdminPdmSettings(**defaults)  # type: ignore[arg-type]


class FakeAdminSettingsRepository:
    def __init__(self, settings: AdminPdmSettings) -> None:
        self._settings = settings

    async def get_pdm(self) -> AdminPdmSettings:
        return self._settings


class FakeGateway:
    def __init__(self) -> None:
        self.variables: dict[int, list[PdmConfigVariables]] = {}
        self.download_result: PdmFileContent | Exception | None = PdmFileContent(
            data=b"%PDF-1.4 fake", content_type="application/pdf"
        )
        self.thumbnail_result: PdmFileContent | Exception | None = PdmFileContent(
            data=_jpeg_bytes(), content_type="image/png"
        )
        self.download_calls: list[int] = []
        self.thumbnail_calls: list[int] = []
        self.variables_calls: list[int] = []

    async def file_variables(self, token: str, file_id: int, version: int, folder_id: int):
        self.variables_calls.append(file_id)
        return self.variables.get(file_id, [])

    async def download_file(self, token: str, file_id: int, version: int, folder_id: int):
        self.download_calls.append(file_id)
        if isinstance(self.download_result, Exception):
            raise self.download_result
        assert self.download_result is not None
        return self.download_result

    async def download_thumbnail(self, token: str, file_id: int, version: int, folder_id: int):
        self.thumbnail_calls.append(file_id)
        if isinstance(self.thumbnail_result, Exception):
            raise self.thumbnail_result
        return self.thumbnail_result


class FakeSession:
    def __init__(self, gateway: FakeGateway) -> None:
        self.gateway = gateway

    async def call(self, fn):
        return await fn(self.gateway, "token")


class FakeMadeItemRepository:
    def __init__(self, items: list[MadeItem] | None = None) -> None:
        self._items = {i.id: i for i in (items or [])}

    async def get_by_id(self, id: int) -> MadeItem | None:
        return self._items.get(id)

    async def get_by_part_number_and_revision(
        self, part_number: str, revision: str
    ) -> MadeItem | None:
        return next(
            (
                i
                for i in self._items.values()
                if not i.archived and i.part_number == part_number and i.revision == revision
            ),
            None,
        )

    async def save(self, item: MadeItem) -> MadeItem:
        self._items[item.id] = item
        return item


class FakeBoughtItemRepository:
    def __init__(self, items: list[BoughtItem] | None = None) -> None:
        self._items = {i.id: i for i in (items or [])}

    async def get_by_id(self, id: int) -> BoughtItem | None:
        return self._items.get(id)

    async def get_by_part_number(self, part_number: str) -> BoughtItem | None:
        return next(
            (i for i in self._items.values() if not i.archived and i.part_number == part_number),
            None,
        )

    async def save(self, item: BoughtItem) -> BoughtItem:
        self._items[item.id] = item
        return item


class FakeMadeItemFileRepository:
    def __init__(self) -> None:
        self.files: list[MadeItemFile] = []
        self._next_id = 1

    async def get_by_item_id_and_category(
        self, item_id: int, category: object
    ) -> list[MadeItemFile]:
        return [f for f in self.files if f.made_item_id == item_id and f.category == category]

    async def save(self, file: MadeItemFile) -> MadeItemFile:
        file.id = self._next_id
        self._next_id += 1
        self.files.append(file)
        return file

    async def delete(self, file: MadeItemFile) -> None:
        self.files = [f for f in self.files if f.id != file.id]


class FakeBoughtItemFileRepository:
    def __init__(self) -> None:
        self.files: list[BoughtItemFile] = []
        self._next_id = 1

    async def get_by_item_id_and_category(
        self, item_id: int, category: object
    ) -> list[BoughtItemFile]:
        return [f for f in self.files if f.bought_item_id == item_id and f.category == category]

    async def save(self, file: BoughtItemFile) -> BoughtItemFile:
        file.id = self._next_id
        self._next_id += 1
        self.files.append(file)
        return file

    async def delete(self, file: BoughtItemFile) -> None:
        self.files = [f for f in self.files if f.id != file.id]


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.uploads: list[str] = []
        self.deletes: list[str] = []

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        self.uploads.append(key)
        self.objects[key] = (data, content_type)

    async def download(self, key: str) -> tuple[bytes, str]:
        return self.objects[key]

    async def delete(self, key: str) -> None:
        self.deletes.append(key)
        self.objects.pop(key, None)

    def get_url(self, key: str, file_name: str | None = None) -> str:
        return f"https://storage.test/{key}"


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


class FakeDocumentLinkRepository:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, int], PdmDocumentLink] = {}
        self.upsert_calls: list[PdmDocumentLink] = []
        self._next_id = 1

    async def get_by_pdm_file(self, vault_id: str, file_id: int) -> PdmDocumentLink | None:
        return self._rows.get((vault_id, file_id))

    async def upsert(self, link: PdmDocumentLink) -> PdmDocumentLink:
        if link.id == 0:
            link.id = self._next_id
            self._next_id += 1
        self._rows[(link.vault_id, link.file_id)] = link
        self.upsert_calls.append(link)
        return link


class FakeUserRepository:
    def __init__(self, user: User) -> None:
        self._user = user

    async def get_by_username(self, username: str) -> User | None:
        return self._user if username == self._user.username else None


class FakeSyncRunRepository:
    def __init__(self) -> None:
        self.entries: list[tuple[int, list]] = []

    async def add_entries(self, run_id: int, entries: list) -> None:
        self.entries.append((run_id, entries))


def make_snapshot(*, file_id: int, kind: str = "document") -> PdmFileSnapshot:
    now = datetime.now(UTC)
    return PdmFileSnapshot(
        id=0,
        vault_id="V1",
        file_id=file_id,
        kind=kind,
        name="CAD-1_A.pdf",
        path="\\Exported Documents\\CAD-1_A.pdf",
        parent_folder_id=5,
        version=3,
        state_id=10,
        state="Released",
        modified_at=None,
        first_seen_at=now,
        last_seen_at=now,
        last_ingested_version=None,
        sync_state=PdmFileSyncState.PENDING,
        last_error=None,
        part_number=None,
        revision=None,
        item_id=None,
        parked_payload=None,
    )


def make_run() -> PdmSyncRun:
    return PdmSyncRun(
        id=1,
        started_at=datetime.now(UTC),
        finished_at=None,
        trigger=PdmSyncTrigger.SCHEDULED,
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
    )


class Rig:
    def __init__(
        self,
        *,
        settings: AdminPdmSettings | None = None,
        made_items: list[MadeItem] | None = None,
        bought_items: list[BoughtItem] | None = None,
        snapshots: list[PdmFileSnapshot] | None = None,
    ) -> None:
        self.gateway = FakeGateway()
        self.session = FakeSession(self.gateway)
        self.settings_repo = FakeAdminSettingsRepository(settings or make_pdm_settings())
        self.made_item_repo = FakeMadeItemRepository(made_items)
        self.bought_item_repo = FakeBoughtItemRepository(bought_items)
        self.snapshot_repo = FakeSnapshotRepository(snapshots)
        self.document_links = FakeDocumentLinkRepository()
        self.user_repo = FakeUserRepository(make_system_user())
        self.made_file_repo = FakeMadeItemFileRepository()
        self.bought_file_repo = FakeBoughtItemFileRepository()
        self.storage = FakeStorage()
        self.uow = FakeUnitOfWork()
        self.run_repo = FakeSyncRunRepository()
        self.picture_repo = FakeItemPictureRepository()
        self.picture_storage = FakePictureStorage()
        self.picture_store = ItemPictureStore(self.picture_repo, self.picture_storage)  # type: ignore[arg-type]

        self.upload_made = UploadMadeItemFile(
            self.made_item_repo,
            self.made_file_repo,
            self.storage,  # type: ignore[arg-type]
            # Their own unit of work, so the read-transaction commit before
            # the storage upload stays out of the sync's commit count.
            uow=FakeUnitOfWork(),
        )
        self.upload_bought = UploadBoughtItemFile(
            self.bought_item_repo,
            self.bought_file_repo,
            self.storage,  # type: ignore[arg-type]
            uow=FakeUnitOfWork(),
        )

        self.sync = PdmDocumentSync(
            self.session,  # type: ignore[arg-type]
            self.settings_repo,  # type: ignore[arg-type]
            self.made_item_repo,  # type: ignore[arg-type]
            self.bought_item_repo,  # type: ignore[arg-type]
            self.snapshot_repo,  # type: ignore[arg-type]
            self.document_links,  # type: ignore[arg-type]
            self.user_repo,  # type: ignore[arg-type]
            upload_made_item_file=self.upload_made,
            upload_bought_item_file=self.upload_bought,
            picture_store=self.picture_store,
            uow=self.uow,
        )
        self.thumbnails = PdmThumbnails(
            self.session,  # type: ignore[arg-type]
            self.settings_repo,  # type: ignore[arg-type]
            self.picture_repo,
            self.picture_store,
            self.user_repo,  # type: ignore[arg-type]
            self.run_repo,  # type: ignore[arg-type]
            self.uow,
        )

    async def cad_rendering(self, kind: ItemKind, item_id: int) -> ItemPicture | None:
        return await self.picture_repo.get_by_source(kind, item_id, ItemPictureSource.CAD_RENDERING)


# ── PdmDocumentSync: matching ────────────────────────────────────────


class TestDatacardMatching:
    async def test_explicit_made_kind_matches_by_part_number_and_revision(self) -> None:
        rig = Rig(made_items=[make_made_item(part_number="CAD-1", revision="A")])
        rig.gateway.variables[1] = [
            PdmConfigVariables(
                configuration_name="@",
                configuration_id=1,
                variables={
                    "PDM.PartNumber": "CAD-1",
                    "PDM.Revision": "A",
                    "Glados.Kind": "made",
                },
            )
        ]
        obj = make_object(id=1)
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])

        outcome = await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_DATACARD, obj=obj)

        assert outcome.action == "document"
        assert outcome.item_id == 1
        assert rig.made_file_repo.files[0].category.value == "drawing"

    async def test_explicit_bought_kind_matches_by_part_number_only(self) -> None:
        rig = Rig(bought_items=[make_bought_item(id=2, part_number="CAD-2")])
        rig.gateway.variables[1] = [
            PdmConfigVariables(
                configuration_name="@",
                configuration_id=1,
                variables={"PDM.BoughtPartNumber": "CAD-2", "Glados.Kind": "bought"},
            )
        ]
        obj = make_object(id=1)
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])

        outcome = await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_DATACARD, obj=obj)

        assert outcome.action == "document"
        assert outcome.item_id == 2
        assert rig.bought_file_repo.files[0].category.value == "drawing"

    async def test_unknown_kind_tries_made_then_bought(self) -> None:
        rig = Rig(bought_items=[make_bought_item(id=2, part_number="CAD-2")])
        # made map resolves no revision (blank), so the made candidate is
        # never even attempted; bought map resolves and matches.
        rig.gateway.variables[1] = [
            PdmConfigVariables(
                configuration_name="@",
                configuration_id=1,
                variables={"PDM.PartNumber": "", "PDM.BoughtPartNumber": "CAD-2"},
            )
        ]
        obj = make_object(id=1)
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])

        outcome = await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_DATACARD, obj=obj)

        assert outcome.action == "document"
        assert outcome.item_id == 2

    async def test_no_match_is_skipped(self) -> None:
        rig = Rig()
        rig.gateway.variables[1] = [
            PdmConfigVariables(
                configuration_name="@",
                configuration_id=1,
                variables={"PDM.PartNumber": "CAD-9", "PDM.Revision": "A"},
            )
        ]
        obj = make_object(id=1)
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])

        outcome = await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_DATACARD, obj=obj)

        assert outcome.action == "skipped"
        assert outcome.message == "no matching item"
        assert outcome.item_id is None

    async def test_missing_identity_variables_is_skipped(self) -> None:
        rig = Rig()
        rig.gateway.variables[1] = [
            PdmConfigVariables(configuration_name="@", configuration_id=1, variables={})
        ]
        obj = make_object(id=1)
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])

        outcome = await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_DATACARD, obj=obj)

        assert outcome.action == "skipped"
        assert outcome.message == "identity variables missing"

    async def test_missing_file_level_configuration_is_skipped(self) -> None:
        # A missing file-level configuration has its own distinct skip
        # reason rather than falling back to whichever configuration comes
        # first.
        rig = Rig()
        rig.gateway.variables[1] = [
            PdmConfigVariables(
                configuration_name="Default",
                configuration_id=1,
                variables={"PDM.PartNumber": "CAD-1", "PDM.Revision": "A"},
            )
        ]
        obj = make_object(id=1)
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])

        outcome = await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_DATACARD, obj=obj)

        assert outcome.action == "skipped"
        assert outcome.message == "no file-level datacard configuration"

    async def test_unmapped_extension_is_skipped(self) -> None:
        rig = Rig(made_items=[make_made_item(part_number="CAD-1", revision="A")])
        rig.gateway.variables[1] = [
            PdmConfigVariables(
                configuration_name="@",
                configuration_id=1,
                variables={"PDM.PartNumber": "CAD-1", "PDM.Revision": "A"},
            )
        ]
        obj = make_object(id=1, name="CAD-1_A.txt")
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])

        outcome = await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_DATACARD, obj=obj)

        assert outcome.action == "skipped"
        assert outcome.message == "extension not mapped"


class TestExcludedKinds:
    def _bought_rig(self, **settings: object) -> Rig:
        rig = Rig(
            settings=make_pdm_settings(**settings),
            bought_items=[make_bought_item(id=2, part_number="CAD-2")],
        )
        rig.gateway.variables[1] = [
            PdmConfigVariables(
                configuration_name="@",
                configuration_id=1,
                variables={"PDM.BoughtPartNumber": "CAD-2", "Glados.Kind": "bought"},
            )
        ]
        return rig

    async def test_an_excluded_kind_skips_the_document_untouched(self) -> None:
        rig = self._bought_rig(document_excluded_kinds={"step": ["bought"]})
        obj = make_object(id=1, name="CAD-2.step")
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])

        outcome = await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_DATACARD, obj=obj)

        assert outcome.action == "skipped"
        assert outcome.message == "extension not ingested for bought items"
        assert rig.bought_file_repo.files == []
        assert await rig.document_links.get_by_pdm_file("V1", 1) is None
        assert is_deliberate_skip(outcome.message)

    async def test_an_exclusion_for_the_other_kind_still_syncs(self) -> None:
        rig = self._bought_rig(document_excluded_kinds={"step": ["made"]})
        obj = make_object(id=1, name="CAD-2.step")
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])

        outcome = await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_DATACARD, obj=obj)

        assert outcome.action == "document"
        assert rig.bought_file_repo.files[0].category.value == "step"


class TestFilenameMatching:
    async def test_extracts_part_number_and_revision(self) -> None:
        rig = Rig(made_items=[make_made_item(part_number="CAD-1", revision="A")])
        obj = make_object(id=1, name="CAD-1_A.pdf")
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])

        outcome = await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_FILENAME, obj=obj)

        assert outcome.action == "document"
        assert outcome.item_id == 1
        assert rig.gateway.variables_calls == []  # filename mode never fetches variables

    async def test_explicit_kind_group_is_honoured(self) -> None:
        rig = Rig(bought_items=[make_bought_item(id=2, part_number="CAD-2")])
        obj = make_object(id=1, name="CAD-2_A_bought.pdf")
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])

        outcome = await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_FILENAME, obj=obj)

        assert outcome.action == "document"
        assert outcome.item_id == 2

    async def test_non_matching_filename_is_skipped(self) -> None:
        rig = Rig()
        obj = make_object(id=1, name="not-a-match.pdf")
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])

        outcome = await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_FILENAME, obj=obj)

        assert outcome.action == "skipped"
        assert outcome.message == "filename does not match the configured pattern"


# ── PdmDocumentSync: download/store/link ─────────────────────────────


class TestDownloadAndStore:
    async def test_new_document_creates_a_link(self) -> None:
        rig = Rig(made_items=[make_made_item(part_number="CAD-1", revision="A")])
        obj = make_object(id=1, version=3)
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])

        outcome = await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_FILENAME, obj=obj)

        assert outcome.action == "document"
        link = await rig.document_links.get_by_pdm_file("V1", 1)
        assert link is not None
        assert link.kind == "made"
        assert link.item_id == 1
        assert link.version == 3
        assert link.item_file_id == rig.made_file_repo.files[0].id

    async def test_new_version_replaces_the_item_file_and_updates_the_link(self) -> None:
        rig = Rig(made_items=[make_made_item(part_number="CAD-1", revision="A")])
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])

        first = make_object(id=1, version=3)
        await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_FILENAME, obj=first)
        first_file_id = rig.made_file_repo.files[0].id

        second = make_object(id=1, version=4)
        outcome = await rig.sync.sync_one(
            vault_id="V1", folder=DOCUMENTS_FOLDER_FILENAME, obj=second
        )

        assert outcome.action == "document"
        # Singleton category: the old file was deleted, exactly one remains.
        assert len(rig.made_file_repo.files) == 1
        assert rig.made_file_repo.files[0].id != first_file_id
        link = await rig.document_links.get_by_pdm_file("V1", 1)
        assert link is not None
        assert link.version == 4
        assert link.item_file_id == rig.made_file_repo.files[0].id

    async def test_image_document_is_stored_as_the_cad_rendering(self) -> None:
        """An `image_and_thumbnail` document becomes the item's CAD rendering,
        not a file, and its link names the picture."""
        rig = Rig(
            settings=make_pdm_settings(document_categories={"jpg": "image_and_thumbnail"}),
            made_items=[make_made_item(part_number="CAD-1", revision="A")],
        )
        rig.gateway.download_result = PdmFileContent(
            data=_jpeg_bytes(size=1200), content_type="application/octet-stream"
        )
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])
        obj = make_object(id=1, name="CAD-1_A.jpg", path="\\Exported Documents\\CAD-1_A.jpg")

        outcome = await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_FILENAME, obj=obj)

        assert outcome.action == "document"
        assert rig.made_file_repo.files == []
        cad = await rig.cad_rendering(ItemKind.MADE, 1)
        assert cad is not None
        assert cad.image_path is not None and cad.thumbnail_path is not None
        link = await rig.document_links.get_by_pdm_file("V1", 1)
        assert link is not None
        assert (link.item_file_id, link.item_picture_id) == (None, cad.id)

    async def test_image_document_leaves_the_photo_alone(self) -> None:
        rig = Rig(
            settings=make_pdm_settings(document_categories={"jpg": "image_and_thumbnail"}),
            bought_items=[make_bought_item(id=2, part_number="CAD-2")],
        )
        rig.picture_repo = FakeItemPictureRepository(
            [make_picture(ItemKind.BOUGHT, 2, ItemPictureSource.PICTURE)]
        )
        rig.picture_store._pictures = rig.picture_repo  # type: ignore[assignment]
        rig.gateway.download_result = PdmFileContent(
            data=_jpeg_bytes(size=64), content_type="application/octet-stream"
        )
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])
        obj = make_object(id=1, name="CAD-2_A_bought.jpg", path="\\Exported Documents\\x.jpg")

        outcome = await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_FILENAME, obj=obj)

        assert outcome.action == "document"
        sources = {p.source for p in rig.picture_repo.pictures.values()}
        assert sources == {ItemPictureSource.PICTURE, ItemPictureSource.CAD_RENDERING}

    async def test_document_outside_a_released_state_is_skipped_untouched(self) -> None:
        """An export still being worked on must never reach an item, and is
        skipped before any datacard read or download."""
        rig = Rig(made_items=[make_made_item(part_number="CAD-1", revision="A")])
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])
        obj = dataclasses.replace(make_object(id=1), state="Editing", state_id=99)

        outcome = await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_DATACARD, obj=obj)

        assert outcome.action == "skipped"
        assert outcome.message == "state not released for documents"
        assert rig.gateway.variables_calls == []
        assert rig.gateway.download_calls == []
        assert rig.made_file_repo.files == []

    async def test_download_error_is_a_document_error(self) -> None:
        rig = Rig(made_items=[make_made_item(part_number="CAD-1", revision="A")])
        rig.gateway.download_result = PdmApiError("boom", status_code=500, body="")
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])
        obj = make_object(id=1)

        outcome = await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_FILENAME, obj=obj)

        assert outcome.action == "document_error"
        assert "boom" in outcome.message
        assert await rig.document_links.get_by_pdm_file("V1", 1) is None

    async def test_snapshot_reflects_the_outcome(self) -> None:
        rig = Rig(made_items=[make_made_item(part_number="CAD-1", revision="A")])
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])
        obj = make_object(id=1)

        await rig.sync.sync_one(vault_id="V1", folder=DOCUMENTS_FOLDER_FILENAME, obj=obj)

        snapshot = await rig.snapshot_repo.get_by_file("V1", 1)
        assert snapshot is not None
        assert snapshot.sync_state == PdmFileSyncState.INGESTED.value
        assert snapshot.item_id == 1
        assert snapshot.part_number == "CAD-1"
        assert snapshot.revision == "A"
        assert snapshot.last_ingested_version == obj.version


# ── PdmThumbnails ─────────────────────────────────────────────────────


class TestThumbnails:
    async def test_disabled_never_calls_the_gateway(self) -> None:
        rig = Rig(settings=make_pdm_settings(thumbnails_enabled=False))
        outcome = IngestOutcome(action="created", item_id=1, message="ok")

        action = await rig.thumbnails.after_ingest(
            "V1", make_object(id=1), "made", outcome, make_run()
        )

        assert action is None
        assert rig.gateway.thumbnail_calls == []

    async def test_unlinked_outcome_never_calls_the_gateway(self) -> None:
        rig = Rig()
        outcome = IngestOutcome(action="created", item_id=None, message="ok")

        action = await rig.thumbnails.after_ingest(
            "V1", make_object(id=1), "made", outcome, make_run()
        )

        assert action is None
        assert rig.gateway.thumbnail_calls == []

    async def test_skipped_outcome_never_calls_the_gateway(self) -> None:
        """A skip action means the file wasn't actually re-synced (no
        version change), so thumbnails must not refresh either."""
        rig = Rig()
        outcome = IngestOutcome(action="skipped", item_id=1, message="already at version 3")

        action = await rig.thumbnails.after_ingest(
            "V1", make_object(id=1), "made", outcome, make_run()
        )

        assert action is None
        assert rig.gateway.thumbnail_calls == []

    async def test_successful_synced_outcome_stores_a_thumbnail_only_cad_rendering(self) -> None:
        rig = Rig(made_items=[make_made_item(id=1)])
        outcome = IngestOutcome(action="revised", item_id=1, message="ok")

        action = await rig.thumbnails.after_ingest(
            "V1", make_object(id=1, version=4), "made", outcome, make_run()
        )

        assert action == "thumbnail"
        cad = await rig.cad_rendering(ItemKind.MADE, 1)
        assert cad is not None
        assert cad.image_path is None
        assert cad.thumbnail_path in rig.picture_storage.blobs

    async def test_bought_item_thumbnail_also_works(self) -> None:
        rig = Rig(bought_items=[make_bought_item(id=2)])
        outcome = IngestOutcome(action="claimed", item_id=2, message="ok")

        action = await rig.thumbnails.after_ingest(
            "V1", make_object(id=1), "bought", outcome, make_run()
        )

        assert action == "thumbnail"
        assert await rig.cad_rendering(ItemKind.BOUGHT, 2) is not None

    async def test_an_exported_image_document_is_never_replaced_by_the_thumbnail(self) -> None:
        rig = Rig(made_items=[make_made_item(id=1)])
        rig.picture_repo.pictures[1] = make_picture(
            ItemKind.MADE, 1, ItemPictureSource.CAD_RENDERING, picture_id=1
        )
        outcome = IngestOutcome(action="revised", item_id=1, message="ok")

        action = await rig.thumbnails.after_ingest(
            "V1", make_object(id=1, version=4), "made", outcome, make_run()
        )

        assert action is None
        assert rig.gateway.thumbnail_calls == []

    async def test_no_thumbnail_available_is_a_quiet_no_op(self) -> None:
        rig = Rig(made_items=[make_made_item(id=1)])
        rig.gateway.thumbnail_result = None
        outcome = IngestOutcome(action="created", item_id=1, message="ok")

        action = await rig.thumbnails.after_ingest(
            "V1", make_object(id=1), "made", outcome, make_run()
        )

        assert action is None
        assert rig.run_repo.entries == []
        assert await rig.cad_rendering(ItemKind.MADE, 1) is None

    async def test_a_thumbnail_that_is_no_image_is_a_thumbnail_error(self) -> None:
        rig = Rig(made_items=[make_made_item(id=1)])
        rig.gateway.thumbnail_result = PdmFileContent(
            data=b"unknown bytes", content_type="application/x-something-weird"
        )
        outcome = IngestOutcome(action="revised", item_id=1, message="ok")

        action = await rig.thumbnails.after_ingest(
            "V1", make_object(id=1, version=4), "made", outcome, make_run()
        )

        assert action == "thumbnail_error"
        assert await rig.cad_rendering(ItemKind.MADE, 1) is None

    async def test_gateway_error_records_a_thumbnail_error_entry(self) -> None:
        rig = Rig(made_items=[make_made_item(id=1)])
        rig.gateway.thumbnail_result = RuntimeError("boom")
        outcome = IngestOutcome(action="created", item_id=1, message="ok")

        action = await rig.thumbnails.after_ingest(
            "V1", make_object(id=1), "made", outcome, make_run()
        )

        assert action == "thumbnail_error"
        assert len(rig.run_repo.entries) == 1
        _, entries = rig.run_repo.entries[0]
        assert entries[0].action == "thumbnail_error"


# ── PdmDocumentSync: one transaction for file row, link and snapshot ──


class TestSyncedDocumentCommitsOnce:
    async def test_file_row_link_and_snapshot_are_written_before_the_one_commit(self) -> None:
        rig = Rig(made_items=[make_made_item(part_number="CAD-1", revision="A")])
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])
        events: list[str] = []
        add_file = rig.made_file_repo.save
        upsert_link = rig.document_links.upsert
        commit = rig.uow.commit

        async def recording_add(file):
            events.append("file")
            return await add_file(file)

        async def recording_upsert(link):
            events.append("link")
            return await upsert_link(link)

        async def recording_commit():
            events.append("commit")
            await commit()

        rig.made_file_repo.save = recording_add  # type: ignore[method-assign]
        rig.document_links.upsert = recording_upsert  # type: ignore[method-assign]
        rig.uow.commit = recording_commit  # type: ignore[method-assign]

        outcome = await rig.sync.sync_one(
            vault_id="V1", folder=DOCUMENTS_FOLDER_FILENAME, obj=make_object(id=1, version=3)
        )

        assert outcome.action == "document"
        assert events == ["file", "link", "commit"]

    async def test_a_failed_commit_rolls_back_and_removes_the_new_blob(self) -> None:
        rig = Rig(made_items=[make_made_item(part_number="CAD-1", revision="A")])
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])
        await rig.sync.sync_one(
            vault_id="V1", folder=DOCUMENTS_FOLDER_FILENAME, obj=make_object(id=1, version=3)
        )
        old_blob = rig.made_file_repo.files[0].storage_path

        async def failing_commit():
            raise RuntimeError("connection lost")

        rig.uow.commit = failing_commit  # type: ignore[method-assign]
        rollbacks_before = rig.uow.rollbacks

        with pytest.raises(RuntimeError, match="connection lost"):
            await rig.sync.sync_one(
                vault_id="V1", folder=DOCUMENTS_FOLDER_FILENAME, obj=make_object(id=1, version=4)
            )

        new_blob = rig.storage.uploads[-1]
        assert new_blob != old_blob
        assert rig.uow.rollbacks == rollbacks_before + 1
        assert new_blob in rig.storage.deletes
        # The replaced document's blob stays: its row was never removed.
        assert old_blob not in rig.storage.deletes

    async def test_a_failed_link_write_removes_the_new_blob_and_is_a_document_error(
        self,
    ) -> None:
        rig = Rig(made_items=[make_made_item(part_number="CAD-1", revision="A")])
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])

        async def failing_upsert(link):
            raise RuntimeError("link write failed")

        rig.document_links.upsert = failing_upsert  # type: ignore[method-assign]

        outcome = await rig.sync.sync_one(
            vault_id="V1", folder=DOCUMENTS_FOLDER_FILENAME, obj=make_object(id=1, version=3)
        )

        assert outcome.action == "document_error"
        assert rig.uow.rollbacks == 1
        assert rig.storage.uploads[-1] in rig.storage.deletes

    async def test_the_replaced_blob_goes_only_after_the_commit(self) -> None:
        rig = Rig(made_items=[make_made_item(part_number="CAD-1", revision="A")])
        await rig.snapshot_repo.upsert_many([make_snapshot(file_id=1)])
        await rig.sync.sync_one(
            vault_id="V1", folder=DOCUMENTS_FOLDER_FILENAME, obj=make_object(id=1, version=3)
        )
        old_blob = rig.made_file_repo.files[0].storage_path
        deletes_at_commit: list[list[str]] = []
        commit = rig.uow.commit

        async def recording_commit():
            deletes_at_commit.append(list(rig.storage.deletes))
            await commit()

        rig.uow.commit = recording_commit  # type: ignore[method-assign]

        await rig.sync.sync_one(
            vault_id="V1", folder=DOCUMENTS_FOLDER_FILENAME, obj=make_object(id=1, version=4)
        )

        assert old_blob not in deletes_at_commit[-1]
        assert old_blob in rig.storage.deletes
