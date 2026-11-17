"""
Unit tests for PdmWriteBack.after_outcome: no database, no HTTP, every port
is an in-memory fake. Covers the gating conditions (disabled, not linked),
the happy path for both kinds (made family with two revisions, one bought
row), the sync-state text for every outcome shape, the two writeback_error
reasons (missing variable, not version-free), the write-all-configurations
path, and that a PDM error never propagates.
"""

import json
from datetime import UTC
from datetime import datetime

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.external_data.application.dto.pdm_dto import IngestOutcome
from src.modules.external_data.application.services.pdm_writeback import PdmWriteBack
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRunEntry
from src.modules.external_data.domain.errors import PdmApiError
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCard
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCardConfiguration
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCardVariable
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo

MADE_VAR_MAP = {
    "part_number": "PDM.PartNumber",
    "revision": "PDM.Revision",
    "kind": "Glados.Kind",
    "glados_ids": "Glados.Ids",
    "newest_revision_sync_state": "Glados.NewestRevisionSyncState",
    "newest_revision_synced_at": "Glados.NewestRevisionSyncedAt",
}

BOUGHT_VAR_MAP = dict(MADE_VAR_MAP)


# ── Entity builders ──────────────────────────────────────────────────


def make_made_item(
    id: int,
    *,
    revision: str = "A",
    vault_id: str = "V1",
    pdm_file_id: int = 100,
    pdm_file_version: int = 5,
    archived: bool = False,
) -> MadeItem:
    return MadeItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=archived,
        revision=revision,
        revision_date=None,
        revision_note=None,
        article_name="Bracket",
        status=MadeItemCatalogueStatus.ACTIVE,
        data_source=DataSource.CAD,
        part_number="CAD-1001",
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
        vault_id=vault_id,
        pdm_file_id=pdm_file_id,
        pdm_file_version=pdm_file_version,
        pdm_synced_at=None,
        pdm_sync_state=None,
        pdm_source_item_id=None,
    )


def make_bought_item(
    id: int,
    *,
    vault_id: str = "V1",
    pdm_file_id: int = 200,
    pdm_file_version: int = 3,
    archived: bool = False,
) -> BoughtItem:
    return BoughtItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=archived,
        article_name="Bolt M6",
        order_code_1="OC-1",
        order_code_2=None,
        gtin=None,
        ean=None,
        tariff_number=None,
        status=BoughtItemCatalogueStatus.ACTIVE,
        data_source=DataSource.CAD,
        part_number="CAD-2001",
        mass=None,
        note=None,
        weblink=None,
        files=[],
        creator_id=1,
        approver_id=None,
        manufacturer_id=1,
        article_group_ids=[],
        successor_item_id=None,
        revision="3",
        vault_id=vault_id,
        pdm_file_id=pdm_file_id,
        pdm_file_version=pdm_file_version,
        pdm_synced_at=None,
        pdm_sync_state=None,
    )


def make_object(
    *, id: int = 100, version: int = 5, parent_folder_id: int = 1, path: str = "\\Made\\part.sldprt"
) -> PdmObjectInfo:
    return PdmObjectInfo(
        id=id,
        name="part.sldprt",
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


def make_variable(
    *, var_id: int, name: str, value: str = "", version_free: bool = True
) -> PdmDataCardVariable:
    return PdmDataCardVariable(
        var_id=var_id,
        name=name,
        value=value,
        var_type=1,
        version_free=version_free,
        read_only=False,
    )


def make_card(
    *,
    variables: list[PdmDataCardVariable] | None = None,
    configuration_name: str = "@",
    extra_configurations: list[PdmDataCardConfiguration] = (),  # type: ignore[assignment]
    write_all: tuple[int, ...] = (),
) -> PdmDataCard:
    default_variables = (
        variables
        if variables is not None
        else [
            make_variable(var_id=1, name="Glados.Ids"),
            make_variable(var_id=2, name="Glados.NewestRevisionSyncState"),
            make_variable(var_id=3, name="Glados.NewestRevisionSyncedAt"),
        ]
    )
    configurations = [
        PdmDataCardConfiguration(id=1, name=configuration_name, variables=tuple(default_variables))
    ]
    configurations.extend(extra_configurations)
    return PdmDataCard(
        configurations=tuple(configurations), variables_with_write_all_configs=write_all
    )


def make_settings(*, writeback_enabled: bool = True) -> AdminPdmSettings:
    return AdminPdmSettings(
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
        writeback_enabled=writeback_enabled,
        made_item_extensions=["sldprt"],
        bought_item_extensions=["sldprt", "sldasm"],
        document_categories={"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
        thumbnails_enabled=False,
        stuck_after_days=7,
        reconcile_requested_deep=None,
        required_fields={"made": [], "bought": []},
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


# ── Fakes ────────────────────────────────────────────────────────────


class FakeGateway:
    def __init__(self) -> None:
        self.datacard_result: PdmDataCard | Exception = make_card()
        self.set_result: bool | Exception = True
        self.set_calls: list[tuple[int, int, dict[str, str]]] = []
        self.datacard_calls: list[tuple[int, int, int]] = []

    async def get_datacard(
        self, token: str, file_id: int, version: int, folder_id: int
    ) -> PdmDataCard:
        self.datacard_calls.append((file_id, version, folder_id))
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
        self.set_calls.append((configuration_id, file_id, dict(values)))
        if isinstance(self.set_result, Exception):
            raise self.set_result
        return self.set_result


class FakeSession:
    def __init__(self, gateway: FakeGateway) -> None:
        self.gateway = gateway

    async def call(self, fn):
        return await fn(self.gateway, "token")


class FakeAdminSettingsRepository:
    def __init__(self, settings: AdminPdmSettings) -> None:
        self.settings = settings

    async def get_pdm(self) -> AdminPdmSettings:
        return self.settings


class FakeMadeItemRepository:
    def __init__(self, items: list[MadeItem] | None = None) -> None:
        self._items = list(items or [])

    async def get_family_by_pdm_file(self, vault_id: str, pdm_file_id: int) -> list[MadeItem]:
        rows = [
            i
            for i in self._items
            if not i.archived and i.vault_id == vault_id and i.pdm_file_id == pdm_file_id
        ]
        rows.sort(key=lambda i: i.revision, reverse=True)
        return rows


class FakeBoughtItemRepository:
    def __init__(self, items: list[BoughtItem] | None = None) -> None:
        self._items = list(items or [])

    async def get_by_pdm_file(self, vault_id: str, pdm_file_id: int) -> BoughtItem | None:
        return next(
            (
                i
                for i in self._items
                if not i.archived and i.vault_id == vault_id and i.pdm_file_id == pdm_file_id
            ),
            None,
        )


class FakeSyncRunRepository:
    def __init__(self) -> None:
        self.entries: list[PdmSyncRunEntry] = []

    async def add_entries(self, run_id: int, entries: list[PdmSyncRunEntry]) -> None:
        self.entries.extend(entries)


class Rig:
    def __init__(
        self,
        *,
        settings: AdminPdmSettings | None = None,
        made_items: list[MadeItem] | None = None,
        bought_items: list[BoughtItem] | None = None,
    ) -> None:
        self.gateway = FakeGateway()
        self.session = FakeSession(self.gateway)
        self.settings_repo = FakeAdminSettingsRepository(settings or make_settings())
        self.made_items = FakeMadeItemRepository(made_items)
        self.bought_items = FakeBoughtItemRepository(bought_items)
        self.runs = FakeSyncRunRepository()
        self.write_back = PdmWriteBack(
            session=self.session,  # type: ignore[arg-type]
            settings_repo=self.settings_repo,  # type: ignore[arg-type]
            made_repo=self.made_items,  # type: ignore[arg-type]
            bought_repo=self.bought_items,  # type: ignore[arg-type]
            run_repo=self.runs,  # type: ignore[arg-type]
        )


def created_outcome(item_id: int = 1) -> IngestOutcome:
    return IngestOutcome(action="created", item_id=item_id, message="created it")


# ── Gating ───────────────────────────────────────────────────────────


async def test_not_linked_does_nothing() -> None:
    rig = Rig()
    outcome = IngestOutcome(action="skipped", item_id=None, message="identity variables missing")

    result = await rig.write_back.after_outcome("V1", make_object(), "made", outcome, make_run())

    assert result is None
    assert rig.runs.entries == []
    assert rig.gateway.datacard_calls == []


async def test_disabled_does_nothing() -> None:
    rig = Rig(
        settings=make_settings(writeback_enabled=False),
        made_items=[make_made_item(1)],
    )

    result = await rig.write_back.after_outcome(
        "V1", make_object(), "made", created_outcome(1), make_run()
    )

    assert result is None
    assert rig.runs.entries == []
    assert rig.gateway.datacard_calls == []


# ── Happy path ───────────────────────────────────────────────────────


async def test_made_family_writes_ids_json_state_and_synced_at() -> None:
    family = [
        make_made_item(1, revision="A", pdm_file_id=100, pdm_file_version=3),
        make_made_item(2, revision="B", pdm_file_id=100, pdm_file_version=5),
    ]
    rig = Rig(made_items=family)

    result = await rig.write_back.after_outcome(
        "V1", make_object(id=100, version=5), "made", created_outcome(2), make_run()
    )

    assert result == "writeback"
    assert len(rig.gateway.set_calls) == 1
    _, _, values = rig.gateway.set_calls[0]

    ids = json.loads(values["Glados.Ids"])
    assert ids == [
        {"revision": "B", "public_id": str(family[1].public_id), "pdm_version": 5},
        {"revision": "A", "public_id": str(family[0].public_id), "pdm_version": 3},
    ]
    assert values["Glados.NewestRevisionSyncState"] == "synced"
    # Real UTC ISO 8601 timestamp, parseable.
    datetime.fromisoformat(values["Glados.NewestRevisionSyncedAt"])

    assert len(rig.runs.entries) == 1
    entry = rig.runs.entries[0]
    assert entry.action == "writeback"
    assert entry.item_id == 2
    assert entry.kind == "made"


async def test_bought_item_writes_one_element_with_null_revision() -> None:
    bought = make_bought_item(1, pdm_file_id=200, pdm_file_version=7)
    rig = Rig(bought_items=[bought])

    result = await rig.write_back.after_outcome(
        "V1", make_object(id=200, version=7), "bought", created_outcome(1), make_run()
    )

    assert result == "writeback"
    _, _, values = rig.gateway.set_calls[0]
    ids = json.loads(values["Glados.Ids"])
    assert ids == [{"revision": None, "public_id": str(bought.public_id), "pdm_version": 7}]


async def test_conflict_outcome_writes_conflict_state() -> None:
    rig = Rig(made_items=[make_made_item(1)])
    outcome = IngestOutcome(action="conflict", item_id=1, message="manufacturer unresolved")

    await rig.write_back.after_outcome("V1", make_object(), "made", outcome, make_run())

    _, _, values = rig.gateway.set_calls[0]
    assert values["Glados.NewestRevisionSyncState"] == "conflict: manufacturer unresolved"


async def test_skipped_outcome_writes_skipped_state() -> None:
    rig = Rig(made_items=[make_made_item(1)])
    outcome = IngestOutcome(action="skipped", item_id=1, message="no in-place changes")

    await rig.write_back.after_outcome("V1", make_object(), "made", outcome, make_run())

    _, _, values = rig.gateway.set_calls[0]
    assert values["Glados.NewestRevisionSyncState"] == "skipped: no in-place changes"


async def test_status_action_counts_as_synced() -> None:
    rig = Rig(made_items=[make_made_item(1)])
    outcome = IngestOutcome(action="status", item_id=1, message="Status set to inactive.")

    await rig.write_back.after_outcome("V1", make_object(), "made", outcome, make_run())

    _, _, values = rig.gateway.set_calls[0]
    assert values["Glados.NewestRevisionSyncState"] == "synced"


# ── Verification failures ───────────────────────────────────────────


async def test_missing_variable_records_writeback_error() -> None:
    card = make_card(
        variables=[
            make_variable(var_id=1, name="Glados.Ids"),
            make_variable(var_id=2, name="Glados.NewestRevisionSyncState"),
            # Glados.NewestRevisionSyncedAt missing entirely.
        ]
    )
    rig = Rig(made_items=[make_made_item(1)])
    rig.gateway.datacard_result = card

    result = await rig.write_back.after_outcome(
        "V1", make_object(), "made", created_outcome(1), make_run()
    )

    assert result == "writeback_error"
    assert rig.gateway.set_calls == []
    assert len(rig.runs.entries) == 1
    entry = rig.runs.entries[0]
    assert entry.action == "writeback_error"
    assert "Glados.NewestRevisionSyncedAt" in entry.message


async def test_not_version_free_records_writeback_error() -> None:
    card = make_card(
        variables=[
            make_variable(var_id=1, name="Glados.Ids", version_free=False),
            make_variable(var_id=2, name="Glados.NewestRevisionSyncState"),
            make_variable(var_id=3, name="Glados.NewestRevisionSyncedAt"),
        ]
    )
    rig = Rig(made_items=[make_made_item(1)])
    rig.gateway.datacard_result = card

    result = await rig.write_back.after_outcome(
        "V1", make_object(), "made", created_outcome(1), make_run()
    )

    assert result == "writeback_error"
    assert rig.gateway.set_calls == []
    assert "Glados.Ids" in rig.runs.entries[0].message


async def test_no_configurations_records_writeback_error() -> None:
    rig = Rig(made_items=[make_made_item(1)])
    rig.gateway.datacard_result = PdmDataCard(
        configurations=(), variables_with_write_all_configs=()
    )

    result = await rig.write_back.after_outcome(
        "V1", make_object(), "made", created_outcome(1), make_run()
    )

    assert result == "writeback_error"
    assert rig.runs.entries[0].message == "no file-level datacard configuration"


# ── Write-all-configurations ────────────────────────────────────────


async def test_write_all_configs_writes_to_every_configuration() -> None:
    second_config = PdmDataCardConfiguration(
        id=2,
        name="Default",
        variables=(
            make_variable(var_id=1, name="Glados.Ids"),
            make_variable(var_id=2, name="Glados.NewestRevisionSyncState"),
            make_variable(var_id=3, name="Glados.NewestRevisionSyncedAt"),
        ),
    )
    card = make_card(extra_configurations=[second_config], write_all=(1,))
    rig = Rig(made_items=[make_made_item(1)])
    rig.gateway.datacard_result = card

    result = await rig.write_back.after_outcome(
        "V1", make_object(), "made", created_outcome(1), make_run()
    )

    assert result == "writeback"
    assert len(rig.gateway.set_calls) == 2
    configuration_ids = {call[0] for call in rig.gateway.set_calls}
    assert configuration_ids == {1, 2}


async def test_default_writes_only_at_configuration() -> None:
    second_config = PdmDataCardConfiguration(
        id=2,
        name="Default",
        variables=(
            make_variable(var_id=1, name="Glados.Ids"),
            make_variable(var_id=2, name="Glados.NewestRevisionSyncState"),
            make_variable(var_id=3, name="Glados.NewestRevisionSyncedAt"),
        ),
    )
    card = make_card(extra_configurations=[second_config])  # no write_all
    rig = Rig(made_items=[make_made_item(1)])
    rig.gateway.datacard_result = card

    await rig.write_back.after_outcome("V1", make_object(), "made", created_outcome(1), make_run())

    assert len(rig.gateway.set_calls) == 1
    assert rig.gateway.set_calls[0][0] == 1


async def test_no_at_configuration_records_writeback_error() -> None:
    # Every SolidWorks file always carries a file-level "@" card, so a card
    # missing one is a writeback_error instead of a silent write onto the
    # first configuration returned ("Default" here).
    card = make_card(configuration_name="Default")
    rig = Rig(made_items=[make_made_item(1)])
    rig.gateway.datacard_result = card

    result = await rig.write_back.after_outcome(
        "V1", make_object(), "made", created_outcome(1), make_run()
    )

    assert result == "writeback_error"
    assert rig.gateway.set_calls == []
    assert rig.runs.entries[0].message == "no file-level datacard configuration"


# ── PDM errors never propagate ───────────────────────────────────────


async def test_get_datacard_error_is_caught_and_recorded() -> None:
    rig = Rig(made_items=[make_made_item(1)])
    rig.gateway.datacard_result = PdmApiError("boom", status_code=500, body="err")

    result = await rig.write_back.after_outcome(
        "V1", make_object(), "made", created_outcome(1), make_run()
    )

    assert result == "writeback_error"
    assert rig.runs.entries[0].action == "writeback_error"
    assert "boom" in rig.runs.entries[0].message


async def test_set_datacard_variables_error_is_caught_and_recorded() -> None:
    rig = Rig(made_items=[make_made_item(1)])
    rig.gateway.set_result = PdmApiError("write failed", status_code=502, body="err")

    result = await rig.write_back.after_outcome(
        "V1", make_object(), "made", created_outcome(1), make_run()
    )

    assert result == "writeback_error"
    assert "write failed" in rig.runs.entries[0].message


async def test_refused_card_read_names_the_step_and_pdm_reason() -> None:
    rig = Rig(made_items=[make_made_item(1)])
    rig.gateway.datacard_result = PdmApiError(
        "PDM call failed with HTTP 403.", status_code=403, body="Access\n  denied"
    )

    await rig.write_back.after_outcome("V1", make_object(), "made", created_outcome(1), make_run())

    assert rig.runs.entries[0].message == (
        "reading the data card failed: PDM call failed with HTTP 403. PDM said: Access denied"
    )


async def test_refused_card_write_names_the_step_and_pdm_reason() -> None:
    rig = Rig(made_items=[make_made_item(1)])
    rig.gateway.set_result = PdmApiError(
        "PDM call failed with HTTP 403.", status_code=403, body="missing permission"
    )

    await rig.write_back.after_outcome("V1", make_object(), "made", created_outcome(1), make_run())

    message = rig.runs.entries[0].message
    assert message.startswith("writing configuration")
    assert message.endswith("PDM said: missing permission")
