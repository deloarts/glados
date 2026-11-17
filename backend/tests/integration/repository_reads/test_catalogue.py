"""
Read scenarios for the item catalogue and master data, including item
files, users, and the devices and variants of products with the lists the
devices pick from. See the package docstring for how the scenarios work.
"""

import dataclasses
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.outbound.persistence.repositories.article_group_repository import (
    SqlAlchemyArticleGroupRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.bought_item_file_repository import (
    SqlAlchemyBoughtItemFileRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.bought_item_repository.item import (
    SqlAlchemyBoughtItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.customer_repository import (
    SqlAlchemyCustomerRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.fabrication_method_repository import (
    SqlAlchemyFabricationMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.inspection_method_repository import (
    SqlAlchemyInspectionMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.item_picture_repository import (
    SqlAlchemyItemPictureRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_file_repository import (
    SqlAlchemyMadeItemFileRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.product_family_repository import (
    SqlAlchemyProductFamilyRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_file_repository import (
    SqlAlchemySourceItemFileRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_repository import (
    SqlAlchemySourceItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_type_repository import (
    SqlAlchemySourceItemTypeRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.supplier_repository import (
    SqlAlchemySupplierRepository,
)
from src.modules.catalogue.domain.entities.bought_item_file import BoughtItemFile
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.entities.item_picture import ItemPicture
from src.modules.catalogue.domain.entities.made_item_file import MadeItemFile
from src.modules.catalogue.domain.entities.source_item_file import SourceItemFile
from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.modules.catalogue.domain.value_objects.source_item_file_category import (
    SourceItemFileCategory,
)
from src.modules.catalogue.ports.outbound.catalogue_queries import ArticleGroupFilterDto
from src.modules.catalogue.ports.outbound.catalogue_queries import BoughtItemFilterDto
from src.modules.catalogue.ports.outbound.catalogue_queries import MadeItemFilterDto
from src.modules.catalogue.ports.outbound.catalogue_queries import ProductFamilyFilterDto
from src.modules.catalogue.ports.outbound.catalogue_queries import SupplierFilterDto
from src.modules.catalogue.ports.outbound.repositories.customer_repository import CustomerFilterDto
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    FabricationMethodFilterDto,
)
from src.modules.catalogue.ports.outbound.repositories.inspection_method_repository import (
    InspectionMethodFilterDto,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    SourceItemFilterDto,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_type_repository import (
    SourceItemTypeFilterDto,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.project_work_repository import (
    SqlAlchemyProjectWork,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.platform.ports.outbound.repositories.user_repository import UserFilterDto
from src.modules.quality.adapters.outbound.persistence.repositories.printer_repository import (
    SqlAlchemyPrinterRepository,
)
from src.modules.quality.ports.outbound.repositories.printer_repository import PrinterFilterDto
from src.modules.workspace.adapters.outbound.persistence.repositories.plc_environment_repository import (
    SqlAlchemyPlcEnvironmentRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.plc_manual_tag_repository import (
    SqlAlchemyPlcManualTagRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_device_check_repository import (
    SqlAlchemyProductDeviceCheckRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_device_repository import (
    SqlAlchemyProductDeviceRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_device_resource_repository import (
    SqlAlchemyProductDeviceKindRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_device_resource_repository import (
    SqlAlchemyProductDeviceOptionRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_file_repository import (
    SqlAlchemyProductFileRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_repository import (
    SqlAlchemyProductRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.product_variant_repository import (
    SqlAlchemyProductVariantRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.plc_environment import PlcEnvironment
from src.modules.workspace.domain.entities.plc_manual_tag import PlcManualTag
from src.modules.workspace.domain.entities.product_device_check import ProductDeviceCheck
from src.modules.workspace.domain.entities.product_file import ProductFile
from src.modules.workspace.domain.entities.product_variant import ProductVariant
from src.modules.workspace.domain.value_objects.device_plan import DevicePlan
from src.modules.workspace.domain.value_objects.product_device_option_category import (
    ProductDeviceOptionCategory,
)
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignalType
from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory
from src.modules.workspace.ports.outbound.repositories.product_repository import ProductFilterDto
from src.modules.workspace.ports.outbound.workspace_queries import ProjectFilterDto
from tests.integration.repository_reads._graph import NOW
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import file_fields
from tests.integration.repository_reads._graph import make
from tests.integration.repository_reads._harness import Scenarios

SCENARIOS = Scenarios()


@SCENARIOS.register(SqlAlchemyMadeItemRepository)
async def _made_items(g: Graph, r: Any) -> None:
    item = await g.made_item()
    process = await g.made_item_process()
    await g.made_item_revision()
    assert item.part_number is not None
    await r.existing_part_numbers([item.part_number])
    await r.get_by_id(item.id)
    await r.get_by_part_number_and_revision(item.part_number, item.revision)
    await r.get_family(item.part_number)
    await r.get_family_by_pdm_file("vault", 12)
    await r.get_multi(MadeItemFilterDto())
    await r.get_process_by_id(process.id)
    await r.get_processes(item.id)
    await r.get_revisions(item.part_number)
    await r.list_cad_items_with_links(None, None)


@SCENARIOS.register(SqlAlchemyBoughtItemRepository)
async def _bought_items(g: Graph, r: Any) -> None:
    item = await g.bought_item()
    assert item.part_number is not None and item.gtin is not None
    await r.existing_part_numbers([item.part_number])
    # A claim candidate is a web-created item without a PDM link.
    web_item = await SqlAlchemyBoughtItemRepository(g.db).save(
        dataclasses.replace(
            item,
            id=0,
            public_id=uuid4(),
            gtin="4006381333948",
            part_number="B-2",
            data_source=DataSource.WEB,
            vault_id=None,
            pdm_file_id=None,
        )
    )
    await g.db.commit()
    await r.find_claim_candidate(gtin=web_item.gtin, manufacturer_id=None, order_code_1=None)
    await r.get_by_gtin(item.gtin)
    await r.get_by_id(item.id)
    await r.get_by_part_number(item.part_number)
    await r.get_by_pdm_file("vault", 11)
    await r.get_multi(BoughtItemFilterDto())
    await r.list_cad_items_with_links(None, None)
    assert await r.find_by_order_code(item.manufacturer_id, " oc 1 ")
    await r.find_by_ean("4006381333955")
    await r.find_by_edp_part_id(451627)


@SCENARIOS.register(SqlAlchemySourceItemRepository)
async def _source_items(g: Graph, r: Any) -> None:
    item = await g.source_item()
    await r.get_aggregate()
    await r.get_by_id(item.id)
    await r.get_by_spec_candidates(item.type_id, item.material, item.manufacturer_id)
    await r.get_multi(SourceItemFilterDto())


@SCENARIOS.register(SqlAlchemyProjectRepository)
async def _projects(g: Graph, r: Any) -> None:
    project = await g.project()
    assert project.product_id is not None
    await r.get_by_designated_user_id(g.uid)
    await r.get_by_id(project.id)
    await r.get_by_product_id(project.product_id)
    await r.get_by_project_number(project.project_number)
    await r.get_multi(ProjectFilterDto())


@SCENARIOS.register(SqlAlchemyProjectWork)
async def _project_work(g: Graph, r: Any) -> None:
    project = await g.project()
    await r.get_live_work(project.id)
    await r.get_live_work_by_ids([project.id])
    await r.get_summary(project.id)


@SCENARIOS.register(SqlAlchemyProductRepository)
async def _products(g: Graph, r: Any) -> None:
    product = await g.product()
    await r.get_active(10)
    await r.get_by_designated_user_id(g.uid)
    await r.get_by_id(product.id)
    await r.get_by_product_number(product.product_number)
    await r.get_multi(ProductFilterDto())


@SCENARIOS.register(SqlAlchemyProductDeviceRepository)
async def _product_devices(g: Graph, r: Any) -> None:
    device = await g.product_device()
    await r.get_by_id(device.id)
    await r.get_by_product(device.product_id, include_archived=False)
    await r.get_by_name(device.product_id, device.name_utf8)
    await r.get_by_ascii_key(device.product_id, device.name_ascii_key)
    await r.get_component_by_eplan_tag(device.product_id, "-MB1")
    await r.max_number(device.product_id, device.group_key)
    await r.count_by_product(device.product_id)
    await r.count_by_driving_medium(device.driving_medium_id)
    await r.count_driven_by(device.id)


@SCENARIOS.register(SqlAlchemyProductDeviceCheckRepository)
async def _product_device_checks(g: Graph, r: Any) -> None:
    device = await g.product_device()
    await SqlAlchemyProductDeviceCheckRepository(g.db).add(
        make(
            ProductDeviceCheck,
            device_id=device.id,
            plan=DevicePlan.EPLAN,
            checked_by_id=g.uid,
            checked_at=NOW,
        )
    )
    await g.db.commit()
    await r.get_by_product(device.product_id)
    await r.get(device.id, DevicePlan.EPLAN)


@SCENARIOS.register(SqlAlchemyPlcManualTagRepository)
async def _plc_manual_tags(g: Graph, r: Any) -> None:
    product = await g.product()
    tag = await SqlAlchemyPlcManualTagRepository(g.db).save(
        make(
            PlcManualTag,
            product_id=product.id,
            name="Light curtain muted",
            signal_type=ProductDeviceSignalType.DI,
            safety=True,
            comment="",
            sort_order=1,
            creator_id=g.uid,
        )
    )
    await g.db.commit()
    await r.get_by_id(tag.id)
    await r.get_by_product(product.id)
    await r.next_sort_order(product.id)


@SCENARIOS.register(SqlAlchemyPlcEnvironmentRepository)
async def _plc_environments(g: Graph, r: Any) -> None:
    environment = await SqlAlchemyPlcEnvironmentRepository(g.db).save(
        make(
            PlcEnvironment,
            name="TIA Portal",
            is_default=True,
            prefixes={"di": "di_"},
            max_tag_length=24,
            tag_table="Tags",
            safety_tag_table="Safety",
            export_sheet="PLC Tags",
            creator_id=g.uid,
        )
    )
    await g.db.commit()
    await r.get_by_id(environment.id)
    await r.get_many(include_archived=False)
    await r.get_live_by_name("TIA Portal")
    await r.get_default()


@SCENARIOS.register(SqlAlchemyProductDeviceOptionRepository)
async def _product_device_options(g: Graph, r: Any) -> None:
    medium = await g.driving_medium()
    assert medium.letter is not None
    await r.get_by_id(medium.id)
    await r.get_by_letter(medium.letter)
    await r.get_many(None, include_archived=False)
    await r.next_sort_order(ProductDeviceOptionCategory.DRIVING_MEDIUM)


@SCENARIOS.register(SqlAlchemyProductDeviceKindRepository)
async def _product_device_kinds(g: Graph, r: Any) -> None:
    kind = await g.device_kind()
    await r.get_by_id(kind.id)
    await r.get_many(include_archived=False)
    await r.next_sort_order()


@SCENARIOS.register(SqlAlchemyProductVariantRepository)
async def _product_variants(g: Graph, r: Any) -> None:
    product = await g.product()
    await SqlAlchemyProductVariantRepository(g.db).save_all(
        product.id, [make(ProductVariant, product_id=product.id, name="Left")]
    )
    await g.db.commit()
    await r.get_by_product(product.id, include_archived=False)


@SCENARIOS.register(SqlAlchemyCustomerRepository)
async def _customers(g: Graph, r: Any) -> None:
    customer = await g.customer()
    assert customer.vat_id is not None
    await r.get_aggregate()
    await r.get_by_id(customer.id)
    await r.get_by_vat_id(customer.vat_id)
    await r.get_multi(CustomerFilterDto())


@SCENARIOS.register(SqlAlchemySupplierRepository)
async def _suppliers(g: Graph, r: Any) -> None:
    supplier = await g.supplier()
    assert supplier.vat_id is not None
    await r.get_aggregate()
    await r.get_by_id(supplier.id)
    await r.get_by_vat_id(supplier.vat_id)
    await r.get_by_edp_code("SIE")
    await r.get_multi(SupplierFilterDto())


async def _named_master_data(r: Any, entity: Any, filters: object) -> None:
    await r.get_aggregate()
    await r.get_by_id(entity.id)
    await r.get_multi(filters)
    await r.get_list_order()
    await r.next_sort_order()


_PLAIN_NAME_LOOKUP = {
    "get_by_name": "matches a plain string name, which only product families have; "
    "localized names are checked through get_live_names"
}


@SCENARIOS.register(SqlAlchemyArticleGroupRepository, exempt=_PLAIN_NAME_LOOKUP)
async def _article_groups(g: Graph, r: Any) -> None:
    group = await g.article_group()
    await _named_master_data(r, group, ArticleGroupFilterDto())
    await r.get_live_names()
    await r.get_by_ids([group.id])


@SCENARIOS.register(
    SqlAlchemyProductFamilyRepository,
    exempt={
        "get_live_names": "reads a localized name map, and product family names are plain "
        "strings; the product family port does not declare it"
    },
)
async def _product_families(g: Graph, r: Any) -> None:
    family = await g.product_family()
    await _named_master_data(r, family, ProductFamilyFilterDto())
    await r.get_by_name(family.name)
    await r.get_by_ids([family.id])


@SCENARIOS.register(SqlAlchemyFabricationMethodRepository, exempt=_PLAIN_NAME_LOOKUP)
async def _fabrication_methods(g: Graph, r: Any) -> None:
    await _named_master_data(r, await g.fabrication_method(), FabricationMethodFilterDto())
    await r.get_live_names()
    await SqlAlchemyFabricationMethodRepository(g.db).save(
        make(
            FabricationMethod,
            name=LocalizedText({"enGB": "Assembly"}),
            default_for_assemblies=True,
            creator_id=g.uid,
        )
    )
    await g.db.commit()
    await r.get_default_for_assemblies()


@SCENARIOS.register(SqlAlchemyInspectionMethodRepository, exempt=_PLAIN_NAME_LOOKUP)
async def _inspection_methods(g: Graph, r: Any) -> None:
    await _named_master_data(r, await g.inspection_method(), InspectionMethodFilterDto())
    await r.get_live_names()


@SCENARIOS.register(SqlAlchemySourceItemTypeRepository, exempt=_PLAIN_NAME_LOOKUP)
async def _source_item_types(g: Graph, r: Any) -> None:
    await _named_master_data(r, await g.source_item_type(), SourceItemTypeFilterDto())
    await r.get_live_names()


@SCENARIOS.register(SqlAlchemyPrinterRepository)
async def _printers(g: Graph, r: Any) -> None:
    printer = await g.printer()
    await r.get_by_id(printer.id)
    await r.get_multi(PrinterFilterDto())


@SCENARIOS.register(SqlAlchemyUserRepository)
async def _users(g: Graph, r: Any) -> None:
    await r.get_by_email(g.user.email)
    await r.get_by_email_ci(g.user.email.upper())
    await r.get_by_id(g.uid)
    await r.maybe_empty.get_by_rfid("0000")
    await r.get_by_username(g.user.username)
    await r.get_by_username_ci(g.user.username.upper())
    await r.get_by_username_or_email(g.user.username)
    await r.get_multi(UserFilterDto())


async def _item_files(r: Any, file: Any, owner_id: int, category: object) -> None:
    await r.get_by_id(file.id)
    await r.get_by_item_id(owner_id)
    await r.get_by_item_id_and_category(owner_id, category)
    await r.get_by_item_ids([owner_id])


@SCENARIOS.register(SqlAlchemyMadeItemFileRepository)
async def _made_item_files(g: Graph, r: Any) -> None:
    item = await g.made_item()
    file = await SqlAlchemyMadeItemFileRepository(g.db).save(
        make(
            MadeItemFile,
            made_item_id=item.id,
            category=MadeItemFileCategory.PDF,
            uploaded_by_user_id=g.uid,
            **file_fields("made"),
        )
    )
    await g.db.commit()
    await _item_files(r, file, item.id, MadeItemFileCategory.PDF)


@SCENARIOS.register(SqlAlchemyBoughtItemFileRepository)
async def _bought_item_files(g: Graph, r: Any) -> None:
    item = await g.bought_item()
    file = await SqlAlchemyBoughtItemFileRepository(g.db).save(
        make(
            BoughtItemFile,
            bought_item_id=item.id,
            category=BoughtItemFileCategory.PDF,
            uploaded_by_user_id=g.uid,
            **file_fields("bought"),
        )
    )
    await g.db.commit()
    await _item_files(r, file, item.id, BoughtItemFileCategory.PDF)


@SCENARIOS.register(SqlAlchemySourceItemFileRepository)
async def _source_item_files(g: Graph, r: Any) -> None:
    item = await g.source_item()
    file = await SqlAlchemySourceItemFileRepository(g.db).save(
        make(
            SourceItemFile,
            source_item_id=item.id,
            category=SourceItemFileCategory.PDF,
            uploaded_by_user_id=g.uid,
            **file_fields("source"),
        )
    )
    await g.db.commit()
    await _item_files(r, file, item.id, SourceItemFileCategory.PDF)


@SCENARIOS.register(SqlAlchemyItemPictureRepository)
async def _item_pictures(g: Graph, r: Any) -> None:
    item = await g.bought_item()
    await SqlAlchemyItemPictureRepository(g.db).save(
        make(
            ItemPicture,
            item_kind=ItemKind.BOUGHT,
            item_id=item.id,
            source=ItemPictureSource.PICTURE,
            uploaded_by_user_id=g.uid,
        )
    )
    await g.db.commit()
    await r.get_by_item(ItemKind.BOUGHT, item.id)
    await r.get_by_items(ItemKind.BOUGHT, [item.id])
    await r.get_by_source(ItemKind.BOUGHT, item.id, ItemPictureSource.PICTURE)


@SCENARIOS.register(SqlAlchemyProductFileRepository)
async def _product_files(g: Graph, r: Any) -> None:
    product = await g.product()
    category = next(iter(ProductFileCategory))
    file = await SqlAlchemyProductFileRepository(g.db).save(
        make(
            ProductFile,
            product_id=product.id,
            category=category,
            uploaded_by_user_id=g.uid,
            **file_fields("product"),
        )
    )
    await g.db.commit()
    await _item_files(r, file, product.id, category)


@SCENARIOS.parametrize
async def test_read_methods_map_without_lazy_loads(repo_cls: type, db: AsyncSession) -> None:
    await SCENARIOS.run(repo_cls, db)
