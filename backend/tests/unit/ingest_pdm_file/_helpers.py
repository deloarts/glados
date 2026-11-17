"""
Plain factory functions and datacard-variable-map constants building
minimal valid entities and settings for the ingest_pdm_file test modules.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.external_data.application.dto.pdm_dto import PdmFilePayload
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from tests import factories

MADE_VAR_MAP = {
    "kind": "Glados.Kind",
    "part_number": "PDM.PartNumber",
    "revision": "PDM.Revision",
    "revision_date": "Glados.RevisionDate",
    "revision_note": "Glados.RevisionNote",
    "article_name": "Glados.ArticleName",
    "material": "Glados.Material",
    "mass": "Glados.Mass",
    "base_size": "Glados.BaseSize",
    "note": "Glados.Note",
    "weblink": "Glados.Weblink",
    "article_group_ids": "Glados.ArticleGroupIds",
    "bought_item_id": "Glados.BoughtItemId",
    "source_item_id": "Glados.SourceItemId",
    "processes": "Glados.Processes",
}

BOUGHT_VAR_MAP = {
    "kind": "Glados.Kind",
    "part_number": "PDM.PartNumber",
    "revision": "PDM.Revision",
    "article_name": "Glados.ArticleName",
    "order_code_1": "Glados.OrderCode1",
    "order_code_2": "Glados.OrderCode2",
    "gtin": "Glados.Gtin",
    "ean": "Glados.Ean",
    "tariff_number": "Glados.TariffNumber",
    "mass": "Glados.Mass",
    "note": "Glados.Note",
    "weblink": "Glados.Weblink",
    "manufacturer_id": "Glados.ManufacturerId",
    "article_group_ids": "Glados.ArticleGroupIds",
}

RELEASED_STATE_ID = 10
OBSOLETE_STATE_ID = 20
REPLACED_STATE_ID = 40
UNWATCHED_STATE_ID = 30

PART_NUMBER_PATTERN = r"CAD-\d+"


def make_user(*, username: str = "system", is_systemuser: bool = True, **overrides: Any) -> User:
    """The system user by default, the account automated ingests are attributed to."""
    return factories.make_user(
        username=username, full_name="System", is_systemuser=is_systemuser, **overrides
    )


def make_made_item(
    id: int,
    *,
    part_number: str | None = None,
    revision: str = "A",
    data_source: DataSource = DataSource.WEB,
    vault_id: str | None = None,
    pdm_file_id: int | None = None,
    pdm_file_version: int | None = None,
    source_item_id: int | None = None,
    pdm_source_item_id: int | None = None,
    article_name: str = "Bracket",
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
        article_name=article_name,
        status=MadeItemCatalogueStatus.ACTIVE,
        data_source=data_source,
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
        source_item_id=source_item_id,
        article_group_ids=[],
        successor_item_id=None,
        changed_by_id=None,
        vault_id=vault_id,
        pdm_file_id=pdm_file_id,
        pdm_file_version=pdm_file_version,
        pdm_synced_at=None,
        pdm_sync_state=None,
        pdm_source_item_id=pdm_source_item_id,
    )


def make_bought_item(
    id: int,
    *,
    part_number: str | None = None,
    data_source: DataSource = DataSource.WEB,
    gtin: str | None = None,
    manufacturer_id: int = 1,
    order_code_1: str = "OC-1",
    vault_id: str | None = None,
    pdm_file_id: int | None = None,
    pdm_file_version: int | None = None,
    revision: str | None = None,
    archived: bool = False,
) -> BoughtItem:
    return BoughtItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=archived,
        article_name="Bolt M6",
        order_code_1=order_code_1,
        order_code_2=None,
        gtin=gtin,
        ean=None,
        tariff_number=None,
        status=BoughtItemCatalogueStatus.ACTIVE,
        data_source=data_source,
        part_number=part_number,
        mass=None,
        note=None,
        weblink=None,
        files=[],
        creator_id=1,
        approver_id=None,
        manufacturer_id=manufacturer_id,
        article_group_ids=[],
        successor_item_id=None,
        revision=revision,
        vault_id=vault_id,
        pdm_file_id=pdm_file_id,
        pdm_file_version=pdm_file_version,
        pdm_synced_at=None,
        pdm_sync_state=None,
    )


def make_article_group(id: int, name: str = "Group") -> ArticleGroup:
    return ArticleGroup(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        name=LocalizedText({"enGB": name}),
        label_color="#999999",
        label_font_color="#000000",
        description=LocalizedText(),
        creator_id=1,
    )


def make_supplier(id: int = 1, name: str = "Acme") -> Supplier:
    return Supplier(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        name=name,
        legal_name=None,
        vat_id=None,
        level=SupplierLevel.A,
        capability_ids=[],
        article_group_ids=[],
        street=None,
        city=None,
        country=None,
        postal_code=None,
        email=None,
        phone=None,
        weblink=None,
        order_email=None,
        order_language=None,
        order_template=None,
        request_email=None,
        request_language=None,
        request_template=None,
        creator_id=1,
    )


def make_source_item(id: int = 1) -> SourceItem:
    return SourceItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        type_id=1,
        dimension=None,
        material="1.0037",
        mass=None,
        note=None,
        order_code_1=None,
        order_code_2=None,
        status=SourceItemCatalogueStatus.ACTIVE,
        creator_id=1,
        approver_id=None,
        manufacturer_id=None,
        successor_item_id=None,
    )


def make_payload(
    *,
    kind: str,
    vault_id: str = "V1",
    file_id: int = 100,
    file_version: int = 5,
    state_id: int = RELEASED_STATE_ID,
    state: str = "Released",
    variables: dict[str, str] | None = None,
    path: str = "\\Made\\part.sldprt",
    name: str = "part.sldprt",
    parent_folder_id: int = 1,
) -> PdmFilePayload:
    return PdmFilePayload(
        vault_id=vault_id,
        file_id=file_id,
        file_version=file_version,
        path=path,
        name=name,
        parent_folder_id=parent_folder_id,
        state_id=state_id,
        state=state,
        kind=kind,
        variables=variables if variables is not None else {},
        modified_at=None,
    )


MADE_VARIABLES = {
    "PDM.PartNumber": "CAD-1001",
    "PDM.Revision": "A",
    "Glados.ArticleName": "Bracket",
    "Glados.Material": "1.0037",
    "Glados.Mass": "123,4",
    "Glados.Note": "from CAD",
}

BOUGHT_VARIABLES = {
    "PDM.PartNumber": "CAD-2001",
    "PDM.Revision": "3",
    "Glados.ArticleName": "Bolt M6",
    "Glados.OrderCode1": "OC-1",
    "Glados.ManufacturerId": "1",
}


def make_pdm_settings(
    *,
    made_map: dict[str, str] | None = None,
    bought_map: dict[str, str] | None = None,
    required_fields: dict[str, list[str]] | None = None,
    made_released_state_ids: list[int] | None = None,
    made_obsolete_state_ids: list[int] | None = None,
    made_replaced_state_ids: list[int] | None = None,
    bought_released_state_ids: list[int] | None = None,
    bought_obsolete_state_ids: list[int] | None = None,
    bought_replaced_state_ids: list[int] | None = None,
    vault_id: str = "",
) -> AdminPdmSettings:
    return AdminPdmSettings(
        id=1,
        made_item_variable_map=made_map if made_map is not None else dict(MADE_VAR_MAP),
        bought_item_variable_map=bought_map if bought_map is not None else dict(BOUGHT_VAR_MAP),
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
        # Same released/obsolete ids for both kinds by default, so a test
        # that only cares about one kind need not set both; a test
        # exercising the per-kind split passes one of these four explicitly.
        made_released_state_ids=(
            made_released_state_ids if made_released_state_ids is not None else [RELEASED_STATE_ID]
        ),
        made_obsolete_state_ids=(
            made_obsolete_state_ids if made_obsolete_state_ids is not None else [OBSOLETE_STATE_ID]
        ),
        made_replaced_state_ids=(
            made_replaced_state_ids if made_replaced_state_ids is not None else [REPLACED_STATE_ID]
        ),
        bought_released_state_ids=(
            bought_released_state_ids
            if bought_released_state_ids is not None
            else [RELEASED_STATE_ID]
        ),
        bought_obsolete_state_ids=(
            bought_obsolete_state_ids
            if bought_obsolete_state_ids is not None
            else [OBSOLETE_STATE_ID]
        ),
        bought_replaced_state_ids=(
            bought_replaced_state_ids
            if bought_replaced_state_ids is not None
            else [REPLACED_STATE_ID]
        ),
        poll_interval_minutes=15,
        vault_id=vault_id,
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
        # Empty by default: only the locked fields (part_number, revision,
        # article_name, and for bought order_code_1/manufacturer_id) apply
        # unless a test opts a kind into more via this parameter; see
        # TestRequiredFields below.
        required_fields=required_fields
        if required_fields is not None
        else {"made": [], "bought": []},
    )


def make_made_item_settings(**overrides: object) -> AdminMadeItemSettings:
    defaults = dict(
        id=1,
        item_number_format="FAB-{yy}-{seq:04d}",
        lot_number_format="LOT-{yy}-{seq:04d}",
        part_number_auto=False,
        part_number_editable=True,
        revision_start="0",
        revision_separator=":",
        revision_skip_ambiguous_letters=False,
        revision_only_newest_editable=True,
        revision_predecessor_status_web="ask",
        revision_predecessor_status_pdm=MadeItemCatalogueStatus.REPLACED.value,
        revision_field_policy=default_policy(),
        web_creation_allowed=True,
        pdm_part_number_pattern=PART_NUMBER_PATTERN,
    )
    defaults.update(overrides)
    return AdminMadeItemSettings(**defaults)  # type: ignore[arg-type]


def make_order_settings(**overrides: object) -> AdminOrderSettings:
    defaults = dict(
        id=1,
        order_number_format="ORD-{yy}-{seq:04d}",
        part_number_format="PUR-{yy}-{seq:04d}",
        part_number_auto=False,
        part_number_editable=True,
        web_creation_allowed=True,
        pdm_part_number_pattern=PART_NUMBER_PATTERN,
    )
    defaults.update(overrides)
    return AdminOrderSettings(**defaults)  # type: ignore[arg-type]
