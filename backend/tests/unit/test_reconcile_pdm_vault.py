"""
Unit tests for ReconcilePdmVault: orchestration around the pure category
helpers (application.services.pdm_reconciliation, covered on their own in
test_pdm_reconciliation.py), paging CAD-owned items, resolving vault_id,
recording the run, and the two categories that need a live lookup instead
of bulk data (`unclaimed_match`, and `writeback_drift` in deep mode only).
No database, no HTTP: the PDM gateway is a small fake behind a
FakeSession that just calls straight through.
"""

import json
from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.part_number_registry import PartNumberRegistryEntry
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.external_data.application.use_cases.pdm.reconcile_pdm_vault import (
    ReconcilePdmVault,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_document_link import PdmDocumentLink
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCard
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCardConfiguration
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCardVariable
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmVaultInfo
from tests.unit.fakes import FakeUnitOfWork

NOW = datetime(2026, 9, 5, 12, 0, 0, tzinfo=UTC)


def make_pdm_settings(**overrides: object) -> AdminPdmSettings:
    defaults: dict[str, object] = dict(
        id=1,
        made_item_variable_map={"glados_ids": "Glados.Ids"},
        bought_item_variable_map={
            "gtin": "Glados.Gtin",
            "order_code_1": "Glados.OrderCode1",
            "part_number": "PDM.PartNumber",
            "glados_ids": "Glados.Ids",
        },
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
        made_replaced_state_ids=[30],
        bought_released_state_ids=[10],
        bought_obsolete_state_ids=[20],
        bought_replaced_state_ids=[30],
        poll_interval_minutes=15,
        vault_id="V1",
        cad_items_read_only=True,
        last_poll_at=None,
        last_poll_error=None,
        last_poll_summary=None,
        writeback_enabled=False,
        made_item_extensions=["sldprt"],
        bought_item_extensions=["sldprt", "sldasm"],
        document_categories={"pdf": "drawing"},
        thumbnails_enabled=False,
        stuck_after_days=7,
        reconcile_requested_deep=None,
        required_fields={"made": [], "bought": []},
    )
    defaults.update(overrides)
    return AdminPdmSettings(**defaults)  # type: ignore[arg-type]


def make_made_item(
    *, id: int = 1, pdm_file_id: int | None = 100, part_number: str = "CAD-1"
) -> MadeItem:
    return MadeItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        revision="A",
        revision_date=None,
        revision_note=None,
        article_name="Part",
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
        pdm_file_id=pdm_file_id,
        pdm_file_version=5,
        pdm_synced_at=None,
        pdm_sync_state=None,
        pdm_source_item_id=None,
    )


def make_bought_item(
    *, id: int = 1, part_number: str = "B-1", gtin: str | None = None
) -> BoughtItem:
    return BoughtItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        article_name="Bought part",
        order_code_1="OC-1",
        order_code_2=None,
        gtin=gtin,
        ean=None,
        tariff_number=None,
        status=BoughtItemCatalogueStatus.ACTIVE,
        data_source=DataSource.WEB,
        part_number=part_number,
        mass=None,
        note=None,
        weblink=None,
        files=[],
        creator_id=1,
        approver_id=None,
        manufacturer_id=None,
        article_group_ids=[],
        successor_item_id=None,
        revision=None,
        vault_id=None,
        pdm_file_id=None,
        pdm_file_version=None,
        pdm_synced_at=None,
        pdm_sync_state=None,
    )


def make_snapshot(
    *,
    file_id: int,
    kind: str | None = "made",
    version: int = 5,
    sync_state: PdmFileSyncState = PdmFileSyncState.INGESTED,
    item_id: int | None = None,
    part_number: str | None = "CAD-1",
    parked_payload: dict[str, str] | None = None,
) -> PdmFileSnapshot:
    return PdmFileSnapshot(
        id=1,
        vault_id="V1",
        file_id=file_id,
        kind=kind,
        name="part.sldprt",
        path="\\Made-Parts\\part.sldprt",
        parent_folder_id=1,
        version=version,
        state_id=10,
        state="Released",
        modified_at=None,
        first_seen_at=NOW,
        last_seen_at=NOW,
        last_ingested_version=version,
        sync_state=sync_state,
        last_error=None,
        part_number=part_number,
        revision="A",
        item_id=item_id,
        parked_payload=parked_payload,
    )


class FakeAdminSettingsRepository:
    def __init__(self, pdm: AdminPdmSettings) -> None:
        self._pdm = pdm
        self.saved_vault_id: str | None = None

    async def get_pdm(self) -> AdminPdmSettings:
        return self._pdm

    async def save_pdm_vault_id(self, vault_id: str) -> None:
        self.saved_vault_id = vault_id
        self._pdm.vault_id = vault_id


class FakeSnapshotRepository:
    def __init__(self, rows: list[PdmFileSnapshot] | None = None) -> None:
        self._rows = rows or []

    async def get_all_for_vault(self, vault_id: str) -> list[PdmFileSnapshot]:
        return [r for r in self._rows if r.vault_id == vault_id]


class FakeMadeItemRepository:
    def __init__(self, items: list[MadeItem] | None = None) -> None:
        self._items = items or []

    async def list_cad_items_with_links(
        self, skip: int | None, limit: int | None
    ) -> tuple[int, list[MadeItem]]:
        items = [i for i in self._items if i.data_source == "CAD"]
        skip = skip or 0
        limit = limit or len(items) or 1
        return len(items), items[skip : skip + limit]

    async def get_revisions(self, part_number: str) -> list[MadeItem]:
        return [i for i in self._items if i.part_number == part_number]

    async def existing_part_numbers(self, part_numbers: list[str]) -> set[str]:
        wanted = set(part_numbers)
        return {i.part_number for i in self._items if i.part_number in wanted}

    async def get_family_by_pdm_file(self, vault_id: str, pdm_file_id: int) -> list[MadeItem]:
        return [i for i in self._items if i.vault_id == vault_id and i.pdm_file_id == pdm_file_id]


class FakeBoughtItemRepository:
    def __init__(self, items: list[BoughtItem] | None = None) -> None:
        self._items = items or []
        self.claim_calls: list[dict[str, object]] = []

    async def list_cad_items_with_links(
        self, skip: int | None, limit: int | None
    ) -> tuple[int, list[BoughtItem]]:
        items = [i for i in self._items if i.data_source == "CAD"]
        skip = skip or 0
        limit = limit or len(items) or 1
        return len(items), items[skip : skip + limit]

    async def get_by_part_number(self, part_number: str) -> BoughtItem | None:
        return next((i for i in self._items if i.part_number == part_number), None)

    async def existing_part_numbers(self, part_numbers: list[str]) -> set[str]:
        wanted = set(part_numbers)
        return {i.part_number for i in self._items if i.part_number in wanted}

    async def get_by_pdm_file(self, vault_id: str, pdm_file_id: int) -> BoughtItem | None:
        return next(
            (i for i in self._items if i.vault_id == vault_id and i.pdm_file_id == pdm_file_id),
            None,
        )

    async def find_claim_candidate(
        self, *, gtin: str | None, manufacturer_id: int | None, order_code_1: str | None
    ) -> BoughtItem | None:
        self.claim_calls.append(
            {"gtin": gtin, "manufacturer_id": manufacturer_id, "order_code_1": order_code_1}
        )
        if gtin:
            matches = [i for i in self._items if i.pdm_file_id is None and i.gtin == gtin]
            return matches[0] if len(matches) == 1 else None
        return None


class FakeDocumentLinkRepository:
    def __init__(self, links: list[PdmDocumentLink] | None = None) -> None:
        self._links = links or []

    async def all_for_vault(self, vault_id: str) -> list[PdmDocumentLink]:
        return [link for link in self._links if link.vault_id == vault_id]


class FakeRegistry:
    def __init__(self, entries: list[PartNumberRegistryEntry] | None = None) -> None:
        self._entries = entries or []

    async def all_entries(self) -> list[PartNumberRegistryEntry]:
        return self._entries


class FakeSupplierRepository:
    async def get_by_id(self, id: int) -> object | None:
        return None


class FakeSyncRunRepository:
    def __init__(self) -> None:
        self._next_id = 1
        self.started: list[PdmSyncRun] = []
        self.finished: list[PdmSyncRun] = []
        self.pruned = False

    async def start(self, run: PdmSyncRun) -> PdmSyncRun:
        run.id = self._next_id
        self._next_id += 1
        self.started.append(run)
        return run

    async def finish(self, run: PdmSyncRun) -> None:
        self.finished.append(run)

    async def prune(self, older_than: datetime) -> int:
        self.pruned = True
        return 0


class FakeFindingRepository:
    def __init__(self) -> None:
        self.added: list = []

    async def add_many(self, findings: list) -> None:
        self.added.extend(findings)


class FakeGateway:
    def __init__(self) -> None:
        self.vault_info_result = PdmVaultInfo(
            vault_id="V1",
            version=1,
            vault_type="SQL",
            archive_server="a",
            database_name="d",
            database_server="s",
        )
        self.datacard_result: PdmDataCard | Exception | None = None

    async def vault_info(self, token: str) -> PdmVaultInfo:
        return self.vault_info_result

    async def get_datacard(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> PdmDataCard:
        if isinstance(self.datacard_result, Exception):
            raise self.datacard_result
        assert self.datacard_result is not None
        return self.datacard_result


class FakeSession:
    def __init__(self, gateway: FakeGateway) -> None:
        self.gateway = gateway

    async def call(self, fn):
        return await fn(self.gateway, "token")


def make_use_case(
    *,
    settings: AdminPdmSettings,
    snapshots: list[PdmFileSnapshot] | None = None,
    made_items: list[MadeItem] | None = None,
    bought_items: list[BoughtItem] | None = None,
    document_links: list[PdmDocumentLink] | None = None,
    registry_entries: list[PartNumberRegistryEntry] | None = None,
    gateway: FakeGateway | None = None,
) -> tuple[ReconcilePdmVault, dict]:
    gateway = gateway or FakeGateway()
    rig = {
        "admin_settings": FakeAdminSettingsRepository(settings),
        "snapshots": FakeSnapshotRepository(snapshots),
        "made_items": FakeMadeItemRepository(made_items),
        "bought_items": FakeBoughtItemRepository(bought_items),
        "document_links": FakeDocumentLinkRepository(document_links),
        "registry": FakeRegistry(registry_entries),
        "runs": FakeSyncRunRepository(),
        "findings": FakeFindingRepository(),
        "uow": FakeUnitOfWork(),
        "gateway": gateway,
    }
    use_case = ReconcilePdmVault(
        session=FakeSession(gateway),
        admin_settings_repo=rig["admin_settings"],
        snapshot_repo=rig["snapshots"],
        made_item_repo=rig["made_items"],
        bought_item_repo=rig["bought_items"],
        document_link_repo=rig["document_links"],
        part_number_registry=rig["registry"],
        supplier_repo=FakeSupplierRepository(),
        run_repo=rig["runs"],
        finding_repo=rig["findings"],
        uow=rig["uow"],
    )
    return use_case, rig


class TestBasicRun:
    async def test_records_a_reconciliation_run(self):
        use_case, rig = make_use_case(settings=make_pdm_settings())
        await use_case.execute(deep=False)
        assert len(rig["runs"].started) == 1
        assert rig["runs"].started[0].trigger == PdmSyncTrigger.RECONCILIATION.value
        assert rig["runs"].started[0].folders_walked == 0
        assert len(rig["runs"].finished) == 1
        assert rig["runs"].finished[0].error is None
        assert rig["runs"].pruned is True

    async def test_no_findings_summary_says_so(self):
        use_case, rig = make_use_case(settings=make_pdm_settings())
        await use_case.execute(deep=False)
        assert rig["runs"].finished[0].summary == "no findings"

    async def test_orphaned_cad_row_finding_is_written(self):
        item = make_made_item(pdm_file_id=None)
        # A registry entry for the item's part number keeps
        # find_items_without_registry_entry quiet, so this test isolates
        # the one finding it means to check.
        registry_entry = PartNumberRegistryEntry(
            part_number=item.part_number, kind=ItemKind.MADE, created=NOW.date()
        )
        use_case, rig = make_use_case(
            settings=make_pdm_settings(), made_items=[item], registry_entries=[registry_entry]
        )
        summary = await use_case.execute(deep=False)
        assert summary.counts.get("orphaned_cad_row") == 1
        assert len(rig["findings"].added) == 1
        finding = rig["findings"].added[0]
        assert finding.run_id == rig["runs"].started[0].id
        assert finding.item_id == item.id

    async def test_resolves_vault_id_when_empty(self):
        settings = make_pdm_settings(vault_id="")
        use_case, rig = make_use_case(settings=settings)
        await use_case.execute(deep=False)
        assert rig["admin_settings"].saved_vault_id == "V1"

    async def test_uow_committed(self):
        use_case, rig = make_use_case(settings=make_pdm_settings())
        await use_case.execute(deep=False)
        assert rig["uow"].committed is True

    async def test_failure_is_recorded_on_the_run_and_reraised(self):
        class ExplodingRegistry(FakeRegistry):
            async def all_entries(self):
                raise RuntimeError("boom")

        settings = make_pdm_settings()
        use_case, rig = make_use_case(settings=settings)
        rig["registry"] = ExplodingRegistry()
        use_case._registry = rig["registry"]  # type: ignore[attr-defined]

        with pytest.raises(RuntimeError, match="boom"):
            await use_case.execute(deep=False)

        assert len(rig["runs"].finished) == 1
        assert rig["runs"].finished[0].error == "boom"


class TestLifecycleStatusCategories:
    """The three lifecycle status categories (docs/PDM_INTEGRATION.md's
    "lifecycle mapping" section), wired through the full run rather than
    unit-tested in isolation (see test_pdm_reconciliation.py for that)."""

    async def test_status_mismatch_finding_is_written(self):
        item = make_made_item(pdm_file_id=100)
        item.status = (
            MadeItemCatalogueStatus.INACTIVE
        )  # snapshot's state_id=10 (released) implies "active"
        registry_entry = PartNumberRegistryEntry(
            part_number=item.part_number, kind=ItemKind.MADE, created=NOW.date()
        )
        snapshot = make_snapshot(file_id=100, item_id=item.id)
        use_case, _rig = make_use_case(
            settings=make_pdm_settings(),
            made_items=[item],
            snapshots=[snapshot],
            registry_entries=[registry_entry],
        )
        summary = await use_case.execute(deep=False)
        assert summary.counts.get("status_mismatch") == 1

    async def test_replaced_without_successor_finding_is_written(self):
        item = make_made_item(pdm_file_id=None)
        item.status = MadeItemCatalogueStatus.REPLACED
        registry_entry = PartNumberRegistryEntry(
            part_number=item.part_number, kind=ItemKind.MADE, created=NOW.date()
        )
        use_case, _rig = make_use_case(
            settings=make_pdm_settings(), made_items=[item], registry_entries=[registry_entry]
        )
        summary = await use_case.execute(deep=False)
        assert summary.counts.get("replaced_without_successor") == 1

    async def test_successor_without_replaced_finding_is_written(self):
        item = make_made_item(pdm_file_id=None)
        item.successor_item_id = 99
        registry_entry = PartNumberRegistryEntry(
            part_number=item.part_number, kind=ItemKind.MADE, created=NOW.date()
        )
        use_case, _rig = make_use_case(
            settings=make_pdm_settings(), made_items=[item], registry_entries=[registry_entry]
        )
        summary = await use_case.execute(deep=False)
        assert summary.counts.get("successor_without_replaced") == 1


class TestPartNumberDrift:
    async def test_drifted_row_yields_one_finding(self):
        item = make_made_item(pdm_file_id=100, part_number="CAD-1")
        registry_entry = PartNumberRegistryEntry(
            part_number=item.part_number, kind=ItemKind.MADE, created=NOW.date()
        )
        snapshot = make_snapshot(file_id=100, item_id=item.id, part_number="CAD-2")
        use_case, rig = make_use_case(
            settings=make_pdm_settings(),
            made_items=[item],
            snapshots=[snapshot],
            registry_entries=[registry_entry],
        )
        summary = await use_case.execute(deep=False)
        assert summary.counts.get("part_number_drift") == 1
        finding = next(f for f in rig["findings"].added if f.category == "part_number_drift")
        assert finding.item_id == item.id


class TestUnclaimedMatch:
    async def test_parked_conflict_matching_web_item_by_gtin_is_reported(self):
        web_item = make_bought_item(id=5, part_number="B-WEB", gtin="4000000000001")
        snapshot = make_snapshot(
            file_id=200,
            kind="bought",
            item_id=None,
            sync_state=PdmFileSyncState.CONFLICT,
            part_number="B-PDM",
            parked_payload={"Glados.Gtin": "4000000000001", "PDM.PartNumber": "B-PDM"},
        )
        use_case, rig = make_use_case(
            settings=make_pdm_settings(), snapshots=[snapshot], bought_items=[web_item]
        )
        summary = await use_case.execute(deep=False)
        assert summary.counts.get("unclaimed_match") == 1
        finding = next(f for f in rig["findings"].added if f.category == "unclaimed_match")
        assert finding.item_id == 5
        assert finding.file_id == 200

    async def test_no_parked_payload_is_not_reported(self):
        snapshot = make_snapshot(
            file_id=200,
            kind="bought",
            item_id=None,
            sync_state=PdmFileSyncState.SKIPPED,
            parked_payload=None,
        )
        use_case, _rig = make_use_case(settings=make_pdm_settings(), snapshots=[snapshot])
        summary = await use_case.execute(deep=False)
        assert "unclaimed_match" not in summary.counts

    async def test_already_linked_snapshot_is_not_reported(self):
        snapshot = make_snapshot(
            file_id=200,
            kind="bought",
            item_id=9,
            sync_state=PdmFileSyncState.INGESTED,
            parked_payload={"Glados.Gtin": "4000000000001"},
        )
        use_case, _rig = make_use_case(settings=make_pdm_settings(), snapshots=[snapshot])
        summary = await use_case.execute(deep=False)
        assert "unclaimed_match" not in summary.counts


class TestQuickModeNeverCallsVault:
    async def test_quick_mode_does_not_read_datacards(self):
        made_item = make_made_item(id=1, pdm_file_id=100)
        snapshot = make_snapshot(file_id=100, kind="made", item_id=1)
        gateway = FakeGateway()
        use_case, _rig = make_use_case(
            settings=make_pdm_settings(vault_id="V1"),
            made_items=[made_item],
            snapshots=[snapshot],
            gateway=gateway,
        )
        summary = await use_case.execute(deep=False)
        assert "writeback_drift" not in summary.counts


class TestDeepModeWritebackDrift:
    def _linked_setup(self, *, card):
        made_item = make_made_item(id=1, pdm_file_id=100)
        snapshot = make_snapshot(file_id=100, kind="made", item_id=1)
        gateway = FakeGateway()
        gateway.datacard_result = card
        return make_use_case(
            settings=make_pdm_settings(),
            made_items=[made_item],
            snapshots=[snapshot],
            gateway=gateway,
        )

    async def test_matching_card_produces_no_drift_finding(self):
        # Built the same way the use case itself computes the expected
        # value, rather than guessing the exact public_id serialization.
        made_item = make_made_item(id=1, pdm_file_id=100)
        expected_ids = json.dumps(
            [
                {
                    "revision": made_item.revision,
                    "public_id": str(made_item.public_id),
                    "pdm_version": made_item.pdm_file_version,
                }
            ]
        )
        card = PdmDataCard(
            configurations=(
                PdmDataCardConfiguration(
                    id=1,
                    name="@",
                    variables=(
                        PdmDataCardVariable(
                            var_id=1,
                            name="Glados.Ids",
                            value=expected_ids,
                            var_type=1,
                            version_free=True,
                            read_only=False,
                        ),
                    ),
                ),
            ),
            variables_with_write_all_configs=(),
        )
        snapshot = make_snapshot(file_id=100, kind="made", item_id=1)
        gateway = FakeGateway()
        gateway.datacard_result = card
        use_case, _rig = make_use_case(
            settings=make_pdm_settings(),
            made_items=[made_item],
            snapshots=[snapshot],
            gateway=gateway,
        )
        summary = await use_case.execute(deep=True)
        assert "writeback_drift" not in summary.counts

    async def test_differing_card_produces_a_warning_finding(self):
        card = PdmDataCard(
            configurations=(
                PdmDataCardConfiguration(
                    id=1,
                    name="@",
                    variables=(
                        PdmDataCardVariable(
                            var_id=1,
                            name="Glados.Ids",
                            value="[]",
                            var_type=1,
                            version_free=True,
                            read_only=False,
                        ),
                    ),
                ),
            ),
            variables_with_write_all_configs=(),
        )
        use_case, rig = self._linked_setup(card=card)
        summary = await use_case.execute(deep=True)
        assert summary.counts.get("writeback_drift") == 1
        finding = next(f for f in rig["findings"].added if f.category == "writeback_drift")
        assert finding.severity == "warning"

    async def test_unreadable_card_produces_an_info_finding_never_aborts(self):
        use_case, rig = self._linked_setup(card=None)
        rig["gateway"].datacard_result = RuntimeError("card unreadable")
        summary = await use_case.execute(deep=True)
        assert summary.counts.get("writeback_drift") == 1
        finding = next(f for f in rig["findings"].added if f.category == "writeback_drift")
        assert finding.severity == "info"
        assert "card unreadable" in finding.message
        # The run itself still succeeded; a per-file drift error is
        # never a run-level failure.
        assert rig["runs"].finished[0].error is None

    async def test_no_at_configuration_produces_a_no_file_level_configuration_finding(self):
        # Every SolidWorks file always carries a file-level "@" card, so a
        # card missing one is its own distinct finding rather than silently
        # comparing against the first configuration's ("Default" here,
        # absent) Glados.Ids value.
        card = PdmDataCard(
            configurations=(
                PdmDataCardConfiguration(
                    id=1,
                    name="Default",
                    variables=(
                        PdmDataCardVariable(
                            var_id=1,
                            name="Glados.Ids",
                            value="[]",
                            var_type=1,
                            version_free=True,
                            read_only=False,
                        ),
                    ),
                ),
            ),
            variables_with_write_all_configs=(),
        )
        use_case, rig = self._linked_setup(card=card)
        summary = await use_case.execute(deep=True)
        assert summary.counts.get("writeback_drift") == 1
        finding = next(f for f in rig["findings"].added if f.category == "writeback_drift")
        assert finding.severity == "info"
        assert finding.message == "no file-level datacard configuration"

    async def test_unmapped_glados_ids_variable_skips_the_check(self):
        made_item = make_made_item(id=1, pdm_file_id=100)
        snapshot = make_snapshot(file_id=100, kind="made", item_id=1)
        gateway = FakeGateway()
        settings = make_pdm_settings(made_item_variable_map={})
        use_case, _rig = make_use_case(
            settings=settings, made_items=[made_item], snapshots=[snapshot], gateway=gateway
        )
        summary = await use_case.execute(deep=True)
        assert "writeback_drift" not in summary.counts
