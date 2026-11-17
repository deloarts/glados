"""
Plain factory functions building minimal valid entities for the made_item
test modules.
"""

from datetime import UTC
from datetime import datetime

from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.platform.domain.value_objects.localized_text import LocalizedText


def make_article_group(id: int = 1, name: str = "Bolts") -> ArticleGroup:
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


def make_source_item(
    id: int = 1, status: SourceItemCatalogueStatus = SourceItemCatalogueStatus.ACTIVE
) -> SourceItem:
    return SourceItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        type_id=1,
        dimension=None,
        material="",
        mass=None,
        note=None,
        order_code_1=None,
        order_code_2=None,
        status=status,
        creator_id=1,
        approver_id=None,
        manufacturer_id=1,
        successor_item_id=None,
    )


def make_bought_item(
    id: int = 1, status: BoughtItemCatalogueStatus = BoughtItemCatalogueStatus.ACTIVE
) -> BoughtItem:
    return BoughtItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        article_name="Alu Round Bar",
        order_code_1="ALU-001",
        order_code_2=None,
        gtin=None,
        ean=None,
        tariff_number=None,
        status=status,
        data_source=DataSource.WEB,
        part_number=None,
        mass=None,
        note=None,
        weblink=None,
        files=[],
        creator_id=1,
        approver_id=None,
        manufacturer_id=1,
        article_group_ids=[],
        successor_item_id=None,
    )


def make_fabrication_method(
    id: int = 1, name: str = "Milling", archived: bool = False
) -> FabricationMethod:
    return FabricationMethod(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        name=LocalizedText({"enGB": name}),
        label_color="#999999",
        label_font_color="#000000",
        description=LocalizedText(),
        creator_id=1,
        archived=archived,
    )


def make_made_item(
    id: int = 1,
    article_name: str = "Bracket",
    status: MadeItemCatalogueStatus = MadeItemCatalogueStatus.ACTIVE,
    archived: bool = False,
    bought_item_id: int | None = None,
    source_item_id: int | None = None,
    part_number: str | None = None,
    revision: str = "A",
    data_source: DataSource = DataSource.WEB,
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
        status=status,
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
        bought_item_id=bought_item_id,
        source_item_id=source_item_id,
        article_group_ids=[],
        successor_item_id=None,
        changed_by_id=None,
    )


def make_process(
    id: int,
    made_item_id: int,
    position: int,
    fabrication_method_id: int | None = 1,
    group_index: int | None = None,
    role: StepRole = StepRole.FABRICATION,
    inspection_method_id: int | None = None,
) -> MadeItemProcess:
    return MadeItemProcess(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        note=None,
        estimated_setup_minutes=None,
        estimated_minutes_per_piece=None,
        creator_id=1,
        fabrication_method_id=fabrication_method_id,
        made_item_id=made_item_id,
        position=position,
        group_index=group_index if group_index is not None else position,
        role=role,
        inspection_method_id=inspection_method_id,
    )


def make_inspection_method(id: int = 1, archived: bool = False) -> InspectionMethod:
    return InspectionMethod(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        name=LocalizedText({"enGB": f"Inspection Method {id}"}),
        label_color="#999999",
        label_font_color="#000000",
        description=LocalizedText(),
        creator_id=1,
        requires_evidence=False,
        archived=archived,
    )


def make_pdm_settings(
    *, enabled: bool = False, cad_items_read_only: bool = True
) -> AdminPdmSettings:
    """is_pdm_enabled() is `enabled and is_configured`, so a caller that
    wants PDM "on" for a test must supply a fully configured connection
    too, not just enabled=True; mirrors AdminPdmSettings.is_configured."""
    return AdminPdmSettings(
        id=1,
        made_item_variable_map={},
        bought_item_variable_map={},
        enabled=enabled,
        base_url="http://pdm-host:65453" if enabled else "",
        vault_name="MyVault" if enabled else "",
        username="svc-account" if enabled else "",
        password="secret" if enabled else None,
        verify_certificate=True,
        timeout_seconds=15,
        session_token=None,
        session_user_id=None,
        session_obtained_at=None,
        watched_folders=[],
        made_released_state_ids=[],
        made_obsolete_state_ids=[],
        made_replaced_state_ids=[],
        bought_released_state_ids=[],
        bought_obsolete_state_ids=[],
        bought_replaced_state_ids=[],
        poll_interval_minutes=15,
        vault_id="",
        cad_items_read_only=cad_items_read_only,
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
