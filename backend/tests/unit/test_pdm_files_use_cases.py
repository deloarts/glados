"""
Unit tests for the admin "PDM files" pending-list use cases (ListPdmFiles,
RetryPdmFile, DismissPdmFile), all against fakes: no network, no database.
Reuses FakeRepo/make_settings from test_pdm_settings_use_cases.py, make_user
from tests/factories.py and FakeEventBus from tests/unit/fakes.py rather than
redefining them.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.external_data.application.dto.pdm_dto import PdmFileSnapshotFilterDto
from src.modules.external_data.application.use_cases.admin_settings.dismiss_pdm_file import (
    DismissPdmFile,
)
from src.modules.external_data.application.use_cases.admin_settings.list_pdm_files import (
    ListPdmFiles,
)
from src.modules.external_data.application.use_cases.admin_settings.retry_pdm_file import (
    RetryPdmFile,
)
from src.modules.external_data.domain.entities.pdm_document_link import PdmDocumentLink
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.errors import AdminSettingsNotFoundError
from src.modules.external_data.domain.events.pdm_events import PdmFileChangeRequested
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    PdmFileSnapshotFilterDto as PdmFileSnapshotFilterPort,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.test_pdm_settings_use_cases import FakeRepo
from tests.unit.test_pdm_settings_use_cases import make_settings

_NOW = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


def make_snapshot(**overrides: object) -> PdmFileSnapshot:
    defaults: dict[str, object] = {
        "id": 1,
        "vault_id": "V1",
        "file_id": 42,
        "kind": "made",
        "name": "Bracket.SLDPRT",
        "path": "\\Made-Parts\\Bracket.SLDPRT",
        "parent_folder_id": 1,
        "version": 3,
        "state_id": 2,
        "state": "Released",
        "modified_at": None,
        "first_seen_at": _NOW,
        "last_seen_at": _NOW,
        "last_ingested_version": None,
        "sync_state": PdmFileSyncState.CONFLICT,
        "last_error": "manufacturer unresolved",
        "part_number": "PN-1",
        "revision": "A",
        "item_id": None,
        "parked_payload": {"PDM.PartNumber": "PN-1"},
    }
    defaults.update(overrides)
    return PdmFileSnapshot(**defaults)  # type: ignore[arg-type]


class FakeSnapshotRepo:
    def __init__(self, snapshots: list[PdmFileSnapshot] | None = None) -> None:
        self._by_id = {s.id: s for s in (snapshots or [])}
        self.get_multi_calls: list[PdmFileSnapshotFilterPort] = []
        self.saved: list[PdmFileSnapshot] = []

    async def get_by_file(self, vault_id: str, file_id: int) -> PdmFileSnapshot | None:
        for s in self._by_id.values():
            if s.vault_id == vault_id and s.file_id == file_id:
                return s
        return None

    async def get_by_id(self, id: int) -> PdmFileSnapshot | None:
        return self._by_id.get(id)

    async def upsert_many(self, items: list[PdmFileSnapshot]) -> None:  # pragma: no cover - unused
        raise NotImplementedError

    async def get_multi(
        self, filters: PdmFileSnapshotFilterPort
    ) -> tuple[int, list[PdmFileSnapshot]]:
        self.get_multi_calls.append(filters)
        rows = list(self._by_id.values())
        if filters.sync_state:
            rows = [r for r in rows if r.sync_state == filters.sync_state]
        if filters.kind:
            rows = [r for r in rows if r.kind == filters.kind]
        if filters.search:
            term = filters.search.lower()
            rows = [
                r
                for r in rows
                if term in r.name.lower()
                or term in r.path.lower()
                or (r.part_number and term in r.part_number.lower())
            ]
        return len(rows), rows

    def mark_missing(self, **kwargs: object) -> list[PdmFileSnapshot]:  # pragma: no cover
        raise NotImplementedError

    async def list_conflicts(self, vault_id: str) -> list[PdmFileSnapshot]:  # pragma: no cover
        raise NotImplementedError

    async def save(self, item: PdmFileSnapshot) -> PdmFileSnapshot:
        self._by_id[item.id] = item
        self.saved.append(item)
        return item

    async def counts_by_state(self, vault_id: str) -> dict[str, int]:  # pragma: no cover
        raise NotImplementedError


def _document_link(
    *, file_id: int, item_id: int, kind: ItemKind = ItemKind.MADE
) -> PdmDocumentLink:
    return PdmDocumentLink(
        id=file_id,
        kind=kind,
        item_id=item_id,
        item_file_id=1,
        vault_id="V1",
        file_id=file_id,
        version=1,
    )


class FakeDocumentLinkRepo:
    def __init__(self, links: list[PdmDocumentLink]) -> None:
        self._links = links
        self.calls: list[tuple[str, list[int]]] = []

    async def get_by_pdm_files(self, vault_id: str, file_ids: list[int]) -> list[PdmDocumentLink]:
        self.calls.append((vault_id, file_ids))
        return [
            link for link in self._links if link.vault_id == vault_id and link.file_id in file_ids
        ]


# ── ListPdmFiles ─────────────────────────────────────────────────────


class TestListPdmFiles:
    async def test_maps_snapshots_and_drops_parked_payload(self):
        repo = FakeSnapshotRepo([make_snapshot(id=1)])
        actor = make_user(permissions=[Permission.READ_SETTINGS])
        use_case = ListPdmFiles(repo)

        total, results = await use_case.execute(actor, PdmFileSnapshotFilterDto())

        assert total == 1
        assert len(results) == 1
        result = results[0]
        assert result.file_id == 42
        assert result.has_parked_payload is True
        assert not hasattr(result, "parked_payload")

    async def test_forwards_filters_to_the_repository(self):
        repo = FakeSnapshotRepo([make_snapshot(id=1)])
        actor = make_user(permissions=[Permission.READ_SETTINGS])
        use_case = ListPdmFiles(repo)

        await use_case.execute(
            actor,
            PdmFileSnapshotFilterDto(
                skip=5, limit=10, sync_state="conflict", kind="made", search="Bracket"
            ),
        )

        assert len(repo.get_multi_calls) == 1
        sent = repo.get_multi_calls[0]
        assert (sent.skip, sent.limit, sent.sync_state, sent.kind, sent.search) == (
            5,
            10,
            "conflict",
            "made",
            "Bracket",
        )

    async def test_requires_read_settings(self):
        repo = FakeSnapshotRepo([make_snapshot(id=1)])
        actor = make_user(permissions=[])
        use_case = ListPdmFiles(repo)

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor, PdmFileSnapshotFilterDto())

    async def test_item_kind_comes_from_the_row_or_its_document_link(self):
        """A document row's own kind is "document"; its item's catalogue
        must come from the document link, or the list links to the wrong
        catalogue."""
        repo = FakeSnapshotRepo(
            [
                make_snapshot(id=1, file_id=10, kind="bought", item_id=3),
                make_snapshot(id=2, file_id=20, kind="document", item_id=9),
                make_snapshot(id=3, file_id=30, kind="document", item_id=None),
                make_snapshot(id=4, file_id=40, kind="document", item_id=5),
            ]
        )
        links = FakeDocumentLinkRepo(
            [
                _document_link(file_id=20, item_id=9, kind=ItemKind.MADE),
                _document_link(file_id=40, item_id=6),
            ]
        )
        actor = make_user(permissions=[Permission.READ_SETTINGS])
        use_case = ListPdmFiles(repo, document_link_repo=links)

        _, results = await use_case.execute(actor, PdmFileSnapshotFilterDto())

        assert {r.id: r.item_kind for r in results} == {1: "bought", 2: "made", 3: None, 4: None}
        assert links.calls == [("V1", [20, 40])]


# ── RetryPdmFile ─────────────────────────────────────────────────────


class TestRetryPdmFile:
    async def test_resets_state_and_publishes_change_requested(self):
        snapshot_repo = FakeSnapshotRepo(
            [make_snapshot(id=1, sync_state=PdmFileSyncState.ERROR, last_error="boom")]
        )
        settings_repo = FakeRepo(make_settings(vault_name="MyVault"))
        bus = FakeEventBus()
        actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        use_case = RetryPdmFile(snapshot_repo, settings_repo, event_bus=bus, uow=FakeUnitOfWork())

        await use_case.execute(actor, snapshot_id=1)

        saved = await snapshot_repo.get_by_id(1)
        assert saved is not None
        assert saved.sync_state == "pending"
        assert saved.last_error is None

        assert len(bus.published) == 1
        event = bus.published[0]
        assert isinstance(event, PdmFileChangeRequested)
        assert event.vault_name == "MyVault"
        assert event.file_id == 42
        assert event.path == "\\Made-Parts\\Bracket.SLDPRT"
        assert event.version is None
        assert event.requested_by_id == actor.id

        assert len(settings_repo.audit_log) == 1
        assert settings_repo.audit_log[0].settings_domain == "pdm"

    async def test_unknown_snapshot_raises_not_found(self):
        snapshot_repo = FakeSnapshotRepo([])
        settings_repo = FakeRepo(make_settings())
        bus = FakeEventBus()
        actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        use_case = RetryPdmFile(snapshot_repo, settings_repo, event_bus=bus, uow=FakeUnitOfWork())

        with pytest.raises(AdminSettingsNotFoundError):
            await use_case.execute(actor, snapshot_id=999)

        assert bus.published == []
        assert settings_repo.audit_log == []

    async def test_retry_by_vault_file_id(self):
        snapshot_repo = FakeSnapshotRepo([make_snapshot(id=7, vault_id="V1", file_id=42)])
        settings = make_settings(vault_name="MyVault")
        settings.vault_id = "V1"
        bus = FakeEventBus()
        actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        use_case = RetryPdmFile(
            snapshot_repo, FakeRepo(settings), event_bus=bus, uow=FakeUnitOfWork()
        )

        await use_case.execute_for_file(actor, file_id=42)

        assert (await snapshot_repo.get_by_id(7)).sync_state == "pending"
        assert bus.published[0].file_id == 42

    async def test_retry_by_unknown_vault_file_id_is_not_found(self):
        settings = make_settings()
        settings.vault_id = "V1"
        use_case = RetryPdmFile(
            FakeSnapshotRepo([]), FakeRepo(settings), event_bus=FakeEventBus(), uow=FakeUnitOfWork()
        )
        actor = make_user(permissions=[Permission.WRITE_SETTINGS])

        with pytest.raises(AdminSettingsNotFoundError):
            await use_case.execute_for_file(actor, file_id=999)

    async def test_requires_write_settings(self):
        snapshot_repo = FakeSnapshotRepo([make_snapshot(id=1)])
        settings_repo = FakeRepo(make_settings())
        bus = FakeEventBus()
        actor = make_user(permissions=[])
        use_case = RetryPdmFile(snapshot_repo, settings_repo, event_bus=bus, uow=FakeUnitOfWork())

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor, snapshot_id=1)
        assert bus.published == []


# ── DismissPdmFile ───────────────────────────────────────────────────


class TestDismissPdmFile:
    async def test_skips_and_clears_parked_payload(self):
        snapshot_repo = FakeSnapshotRepo(
            [
                make_snapshot(
                    id=1,
                    sync_state=PdmFileSyncState.CONFLICT,
                    parked_payload={"PDM.PartNumber": "PN-1"},
                )
            ]
        )
        settings_repo = FakeRepo(make_settings())
        actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        use_case = DismissPdmFile(snapshot_repo, settings_repo, uow=FakeUnitOfWork())

        result = await use_case.execute(actor, snapshot_id=1)

        assert result.sync_state == "skipped"
        assert result.last_error == f"dismissed by {actor.username}"
        assert result.has_parked_payload is False

        saved = await snapshot_repo.get_by_id(1)
        assert saved is not None
        assert saved.parked_payload is None
        assert saved.sync_state == "skipped"
        assert saved.last_error == f"dismissed by {actor.username}"

        assert len(settings_repo.audit_log) == 1
        assert settings_repo.audit_log[0].settings_domain == "pdm"

    async def test_dismissed_document_row_keeps_its_item_kind(self):
        """The frontend swaps the returned row into its list, so it must
        carry the same item catalogue the list would show."""
        snapshot_repo = FakeSnapshotRepo(
            [
                make_snapshot(
                    id=1, file_id=20, kind="document", item_id=9, sync_state=PdmFileSyncState.ERROR
                )
            ]
        )
        settings_repo = FakeRepo(make_settings())
        actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        use_case = DismissPdmFile(
            snapshot_repo,
            settings_repo,
            uow=FakeUnitOfWork(),
            document_link_repo=FakeDocumentLinkRepo([_document_link(file_id=20, item_id=9)]),
        )

        result = await use_case.execute(actor, snapshot_id=1)

        assert result.item_kind == "made"

    async def test_unknown_snapshot_raises_not_found(self):
        snapshot_repo = FakeSnapshotRepo([])
        settings_repo = FakeRepo(make_settings())
        actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        use_case = DismissPdmFile(snapshot_repo, settings_repo, uow=FakeUnitOfWork())

        with pytest.raises(AdminSettingsNotFoundError):
            await use_case.execute(actor, snapshot_id=999)
        assert settings_repo.audit_log == []

    async def test_requires_write_settings(self):
        snapshot_repo = FakeSnapshotRepo([make_snapshot(id=1)])
        settings_repo = FakeRepo(make_settings())
        actor = make_user(permissions=[])
        use_case = DismissPdmFile(snapshot_repo, settings_repo, uow=FakeUnitOfWork())

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor, snapshot_id=1)
