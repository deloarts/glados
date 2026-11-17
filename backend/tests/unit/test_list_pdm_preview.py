"""
Unit tests for ListPdmPreview: no database, no HTTP, every port is an
in-memory fake.
"""

from datetime import UTC
from datetime import datetime

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.external_data.application.use_cases.pdm.list_pdm_preview import ListPdmPreview
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from tests.factories import make_user

VAULT_ID = "V1"


def make_made_item(
    id: int, *, part_number: str | None, revision: str = "A", pdm_file_version: int | None = None
) -> MadeItem:
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
        material="1.0037",
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
        vault_id=VAULT_ID,
        pdm_file_id=100,
        pdm_file_version=pdm_file_version,
        pdm_synced_at=None,
        pdm_sync_state=None,
        pdm_source_item_id=None,
    )


def make_bought_item(
    id: int, *, part_number: str | None, pdm_file_version: int | None = None
) -> BoughtItem:
    return BoughtItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        article_name="Bolt M6",
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
        vault_id=VAULT_ID,
        pdm_file_id=200,
        pdm_file_version=pdm_file_version,
        pdm_synced_at=None,
        pdm_sync_state=None,
    )


def make_snapshot(
    *,
    file_id: int,
    kind: str | None,
    part_number: str | None,
    revision: str | None = "A",
    version: int = 1,
    item_id: int | None = None,
    sync_state: PdmFileSyncState = PdmFileSyncState.SKIPPED,
    article_name: str | None = "Bracket",
) -> PdmFileSnapshot:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return PdmFileSnapshot(
        id=file_id,
        vault_id=VAULT_ID,
        file_id=file_id,
        kind=kind,
        name=f"file-{file_id}.sldprt",
        path=f"\\Made\\file-{file_id}.sldprt",
        parent_folder_id=1,
        version=version,
        state_id=10,
        state="Released",
        modified_at=now,
        first_seen_at=now,
        last_seen_at=now,
        last_ingested_version=None,
        sync_state=sync_state,
        last_error=None,
        part_number=part_number,
        revision=revision,
        item_id=item_id,
        parked_payload=None,
        article_name=article_name,
    )


def make_pdm_settings(*, enabled: bool = True, vault_id: str = VAULT_ID) -> AdminPdmSettings:
    return AdminPdmSettings(
        id=1,
        made_item_variable_map={},
        bought_item_variable_map={},
        enabled=enabled,
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
        vault_id=vault_id,
        cad_items_read_only=True,
        last_poll_at=None,
        last_poll_error=None,
        last_poll_summary=None,
        writeback_enabled=False,
        made_item_extensions=["sldprt"],
        bought_item_extensions=["sldprt", "sldasm"],
        document_categories={},
        thumbnails_enabled=False,
        stuck_after_days=7,
        reconcile_requested_deep=None,
        required_fields={"made": [], "bought": []},
    )


class FakeMadeItemRepository:
    def __init__(self, items: list[MadeItem] | None = None) -> None:
        self._items = {i.id: i for i in (items or [])}

    async def get_by_id(self, id: int) -> MadeItem | None:
        return self._items.get(id)

    async def get_revisions(self, part_number: str) -> list[MadeItem]:
        return [i for i in self._items.values() if i.part_number == part_number and not i.archived]

    async def existing_part_numbers(self, part_numbers: list[str]) -> set[str]:
        live = {i.part_number for i in self._items.values() if not i.archived}
        return {p for p in part_numbers if p in live}


class FakeBoughtItemRepository:
    def __init__(self, items: list[BoughtItem] | None = None) -> None:
        self._items = {i.id: i for i in (items or [])}

    async def get_by_id(self, id: int) -> BoughtItem | None:
        return self._items.get(id)

    async def get_by_part_number(self, part_number: str) -> BoughtItem | None:
        return next(
            (i for i in self._items.values() if i.part_number == part_number and not i.archived),
            None,
        )

    async def existing_part_numbers(self, part_numbers: list[str]) -> set[str]:
        live = {i.part_number for i in self._items.values() if not i.archived}
        return {p for p in part_numbers if p in live}


class FakePdmFileSnapshotRepository:
    def __init__(self, rows: list[PdmFileSnapshot] | None = None) -> None:
        self._rows = rows or []

    async def get_all_for_vault(self, vault_id: str) -> list[PdmFileSnapshot]:
        return [r for r in self._rows if r.vault_id == vault_id]

    async def get_preview_candidates(self, vault_id: str, kind: str) -> list[PdmFileSnapshot]:
        # Mirrors the repository's SQL filter.
        return [
            r
            for r in self._rows
            if r.vault_id == vault_id
            and r.kind == kind
            and r.part_number
            and r.sync_state != "missing"
            and (
                r.item_id is None
                or r.last_ingested_version is None
                or r.version > r.last_ingested_version
            )
        ]


class FakeAdminSettingsRepository:
    def __init__(self, pdm: AdminPdmSettings) -> None:
        self._pdm = pdm

    async def get_pdm(self) -> AdminPdmSettings:
        return self._pdm


def make_use_case(
    *,
    snapshots: list[PdmFileSnapshot] | None = None,
    made_items: list[MadeItem] | None = None,
    bought_items: list[BoughtItem] | None = None,
    pdm_settings: AdminPdmSettings | None = None,
) -> ListPdmPreview:
    return ListPdmPreview(
        snapshot_repo=FakePdmFileSnapshotRepository(snapshots),  # type: ignore[arg-type]
        made_item_repo=FakeMadeItemRepository(made_items),  # type: ignore[arg-type]
        bought_item_repo=FakeBoughtItemRepository(bought_items),  # type: ignore[arg-type]
        admin_settings_repo=FakeAdminSettingsRepository(  # type: ignore[arg-type]
            pdm_settings or make_pdm_settings()
        ),
    )


class TestDisabledIntegration:
    async def test_disabled_returns_empty_lists(self) -> None:
        use_case = make_use_case(
            snapshots=[make_snapshot(file_id=1, kind="made", part_number="CAD-1")],
            pdm_settings=make_pdm_settings(enabled=False),
        )
        result = await use_case.execute(make_user(), "made")
        assert result.enabled is False
        assert result.unlinked == []
        assert result.newer == []

    async def test_no_vault_id_returns_empty_lists(self) -> None:
        use_case = make_use_case(
            snapshots=[make_snapshot(file_id=1, kind="made", part_number="CAD-1")],
            pdm_settings=make_pdm_settings(vault_id=""),
        )
        result = await use_case.execute(make_user(), "made")
        assert result.enabled is False
        assert result.unlinked == []
        assert result.newer == []


class TestUnlinked:
    async def test_unlinked_excludes_part_numbers_that_already_exist(self) -> None:
        existing = make_made_item(1, part_number="CAD-EXISTING")
        use_case = make_use_case(
            snapshots=[
                make_snapshot(file_id=1, kind="made", part_number="CAD-EXISTING"),
                make_snapshot(file_id=2, kind="made", part_number="CAD-NEW"),
            ],
            made_items=[existing],
        )
        result = await use_case.execute(make_user(), "made")
        assert result.enabled is True
        assert [f.part_number for f in result.unlinked] == ["CAD-NEW"]
        assert result.newer == []

    async def test_unlinked_ignores_other_kind_and_missing_sync_state(self) -> None:
        use_case = make_use_case(
            snapshots=[
                make_snapshot(file_id=1, kind="bought", part_number="CAD-BOUGHT"),
                make_snapshot(
                    file_id=2,
                    kind="made",
                    part_number="CAD-GONE",
                    sync_state=PdmFileSyncState.MISSING,
                ),
            ],
        )
        result = await use_case.execute(make_user(), "made")
        assert result.unlinked == []

    async def test_unlinked_carries_article_name_and_file_identity(self) -> None:
        use_case = make_use_case(
            snapshots=[
                make_snapshot(
                    file_id=1, kind="made", part_number="CAD-NEW", article_name="New Bracket"
                )
            ],
        )
        result = await use_case.execute(make_user(), "made")
        assert len(result.unlinked) == 1
        file = result.unlinked[0]
        assert file.file_id == 1
        assert file.part_number == "CAD-NEW"
        assert file.article_name == "New Bracket"


class TestNewer:
    async def test_newer_requires_snapshot_version_greater_than_item(self) -> None:
        behind = make_made_item(1, part_number="CAD-1", pdm_file_version=2)
        up_to_date = make_made_item(2, part_number="CAD-2", pdm_file_version=5)
        use_case = make_use_case(
            snapshots=[
                make_snapshot(file_id=10, kind="made", part_number="CAD-1", version=3, item_id=1),
                make_snapshot(file_id=11, kind="made", part_number="CAD-2", version=5, item_id=2),
            ],
            made_items=[behind, up_to_date],
        )
        result = await use_case.execute(make_user(), "made")
        assert [n.item_id for n in result.newer] == [1]
        assert result.newer[0].version == 3
        assert result.unlinked == []

    async def test_newer_included_when_item_has_no_pdm_file_version_yet(self) -> None:
        item = make_made_item(1, part_number="CAD-1", pdm_file_version=None)
        use_case = make_use_case(
            snapshots=[
                make_snapshot(file_id=10, kind="made", part_number="CAD-1", version=1, item_id=1)
            ],
            made_items=[item],
        )
        result = await use_case.execute(make_user(), "made")
        assert [n.item_id for n in result.newer] == [1]

    async def test_newer_skips_rows_whose_linked_item_is_gone(self) -> None:
        use_case = make_use_case(
            snapshots=[
                make_snapshot(file_id=10, kind="made", part_number="CAD-1", version=3, item_id=999)
            ],
        )
        result = await use_case.execute(make_user(), "made")
        assert result.newer == []

    async def test_bought_newer_uses_bought_repository(self) -> None:
        item = make_bought_item(1, part_number="CAD-B1", pdm_file_version=1)
        use_case = make_use_case(
            snapshots=[
                make_snapshot(file_id=20, kind="bought", part_number="CAD-B1", version=2, item_id=1)
            ],
            bought_items=[item],
        )
        result = await use_case.execute(make_user(), "bought")
        assert [n.item_id for n in result.newer] == [1]


class TestReadIsOpenToAnyActiveUser:
    """ListPdmPreview mirrors GetMadeItems/GetBoughtItems: neither list
    endpoint gates reads by permission, so a viewer with no permissions at
    all still gets a result rather than an InsufficientPermissionsError;
    there is no "permission denied" case to test because none of the
    read paths this use case mirrors has one (see the module's own
    docstring, matching GetLookups's precedent)."""

    async def test_actor_without_any_permission_still_gets_a_result(self) -> None:
        use_case = make_use_case(
            snapshots=[make_snapshot(file_id=1, kind="made", part_number="CAD-NEW")],
        )
        result = await use_case.execute(make_user(permissions=[]), "made")
        assert result.enabled is True
        assert len(result.unlinked) == 1
