"""
PDM folder ids/watched-folder constants and plain factory functions shared
by the poll_pdm_vault test modules.
"""

from datetime import UTC
from datetime import datetime
from typing import cast

from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCard
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCardConfiguration
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmDataCardVariable
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo

# PDM folder ids used throughout: the vault root is always 1, the three
# watched folders below resolve to these fixed ids via the gateway's
# pre-seeded root listing (see FakeGateway.__init__).
ROOT_ID = 1
MADE_FOLDER_ID = 10
BOUGHT_FOLDER_ID = 20
BY_KIND_FOLDER_ID = 30
# A subfolder id no test's FakeGateway ever seeds; stands in for "a folder
# this run never visited" (deleted, or simply outside every watched tree).
_SUB_FOLDER_ID = 11
_OUTSIDE_FOLDER_ID = 999

MADE_FOLDER = PdmWatchedFolder(path="\\Made-Parts", kind="made", recursive=True, enabled=True)
MADE_FOLDER_FLAT = PdmWatchedFolder(path="\\Made-Parts", kind="made", recursive=False, enabled=True)
BOUGHT_FOLDER = PdmWatchedFolder(path="\\Bought-Parts", kind="bought", recursive=True, enabled=True)
BY_KIND_FOLDER = PdmWatchedFolder(path="\\Parts", kind="by_kind", recursive=True, enabled=True)
DOCUMENTS_FOLDER_ID = 40
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
    id: int,
    name: str = "part.sldprt",
    path: str = "\\Made-Parts\\part.sldprt",
    version: int = 5,
    state_id: int = 10,
    state: str = "Released",
    parent_folder_id: int = MADE_FOLDER_ID,
    is_deleted: bool = False,
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
        is_deleted=is_deleted,
    )


def make_folder(
    *,
    id: int,
    name: str,
    path: str,
    parent_folder_id: int = ROOT_ID,
    is_deleted: bool = False,
) -> PdmObjectInfo:
    return PdmObjectInfo(
        id=id,
        name=name,
        size=0,
        modified_at=None,
        version=0,
        state="",
        state_id=0,
        parent_folder_id=parent_folder_id,
        path=path,
        object_type=0,
        is_locked=False,
        locked_by=0,
        is_shared=False,
        is_toolbox=False,
        is_deleted=is_deleted,
    )


def make_snapshot(
    *,
    vault_id: str = "V1",
    file_id: int,
    kind: str | None = "made",
    path: str = "\\Made-Parts\\part.sldprt",
    # Matches MADE_FOLDER_ID, the default watched folder's own id most
    # tests that build a snapshot without caring about it are actually
    # under; _sweep_missing attributes a snapshot to a
    # watched folder by this field, not by its path, so it must agree
    # with whichever folder a test's own walk is expected to visit.
    parent_folder_id: int = MADE_FOLDER_ID,
    version: int = 5,
    state_id: int = 10,
    state: str = "Released",
    sync_state: PdmFileSyncState = PdmFileSyncState.INGESTED,
    last_seen_at: datetime | None = None,
    item_id: int | None = None,
) -> PdmFileSnapshot:
    now = datetime.now(UTC)
    return PdmFileSnapshot(
        id=1,
        vault_id=vault_id,
        file_id=file_id,
        kind=kind,
        name="part.sldprt",
        path=path,
        parent_folder_id=parent_folder_id,
        version=version,
        state_id=state_id,
        state=state,
        modified_at=None,
        first_seen_at=now,
        last_seen_at=last_seen_at or now,
        last_ingested_version=version,
        sync_state=sync_state,
        last_error=None,
        part_number="CAD-1",
        revision="A",
        item_id=item_id,
        parked_payload=None,
    )


def make_pdm_settings(
    *, watched_folders: list[PdmWatchedFolder] | None = None, **overrides: object
) -> AdminPdmSettings:
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
        watched_folders=watched_folders if watched_folders is not None else [MADE_FOLDER],
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


def make_made_item(id: int) -> MadeItem:
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
        part_number="CAD-1",
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
        pdm_file_id=id,
        pdm_file_version=5,
        pdm_synced_at=None,
        pdm_sync_state=None,
        pdm_source_item_id=None,
    )
