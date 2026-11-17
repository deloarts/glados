"""Use case factories: bought/made/source items, source item types, article groups,
fabrication methods.
"""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.bindings import get_bought_item_usages
from src.modules.catalogue.adapters.inbound.api.deps.bindings import get_cad_source
from src.modules.catalogue.adapters.inbound.api.deps.bindings import get_default_machine_lookup
from src.modules.catalogue.adapters.inbound.api.deps.bindings import get_inspection_method_usage
from src.modules.catalogue.adapters.inbound.api.deps.bindings import get_made_item_usages
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_article_group_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_bought_item_file_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_bought_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_catalogue_settings_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_customer_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_fabrication_method_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_inspection_method_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_item_picture_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_made_item_file_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_made_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import (
    get_part_number_registry_repo,
)
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_product_family_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_source_item_file_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_source_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_source_item_type_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_supplier_repo
from src.modules.catalogue.application.use_cases.article_group.archive_article_group import (
    ArchiveArticleGroup,
)
from src.modules.catalogue.application.use_cases.article_group.create_article_group import (
    CreateArticleGroup,
)
from src.modules.catalogue.application.use_cases.article_group.get_article_group import (
    GetArticleGroup,
)
from src.modules.catalogue.application.use_cases.article_group.get_article_group import (
    GetArticleGroups,
)
from src.modules.catalogue.application.use_cases.article_group.move_article_group import (
    MoveArticleGroup,
)
from src.modules.catalogue.application.use_cases.article_group.move_article_group import (
    PlaceArticleGroup,
)
from src.modules.catalogue.application.use_cases.article_group.restore_article_group import (
    RestoreArticleGroup,
)
from src.modules.catalogue.application.use_cases.article_group.update_article_group import (
    UpdateArticleGroup,
)
from src.modules.catalogue.application.use_cases.bought_item.archive_bought_item import (
    ArchiveBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.create_bought_item import (
    CreateBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.delete_bought_item_file import (
    DeleteBoughtItemFile,
)
from src.modules.catalogue.application.use_cases.bought_item.download_bought_item_file import (
    DownloadBoughtItemFile,
)
from src.modules.catalogue.application.use_cases.bought_item.get_bought_item import GetBoughtItem
from src.modules.catalogue.application.use_cases.bought_item.get_bought_item import GetBoughtItems
from src.modules.catalogue.application.use_cases.bought_item.get_bought_item_files import (
    GetBoughtItemFiles,
)
from src.modules.catalogue.application.use_cases.bought_item.list_bought_item_merge_targets import (
    ListBoughtItemMergeTargets,
)
from src.modules.catalogue.application.use_cases.bought_item.merge_bought_item import (
    MergeBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.restore_bought_item import (
    RestoreBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.update_bought_item import (
    UpdateBoughtItem,
)
from src.modules.catalogue.application.use_cases.bought_item.update_bought_item_file import (
    UpdateBoughtItemFile,
)
from src.modules.catalogue.application.use_cases.bought_item.upload_bought_item_file import (
    UploadBoughtItemFile,
)
from src.modules.catalogue.application.use_cases.fabrication_method.archive_fabrication_method import (
    ArchiveFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.create_fabrication_method import (
    CreateFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.get_fabrication_method import (
    GetAssemblyDefaultFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.get_fabrication_method import (
    GetFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.get_fabrication_method import (
    GetFabricationMethods,
)
from src.modules.catalogue.application.use_cases.fabrication_method.move_fabrication_method import (
    MoveFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.move_fabrication_method import (
    PlaceFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.restore_fabrication_method import (
    RestoreFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.update_fabrication_method import (
    UpdateFabricationMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.archive_inspection_method import (
    ArchiveInspectionMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.create_inspection_method import (
    CreateInspectionMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.get_inspection_method import (
    GetInspectionMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.get_inspection_method import (
    GetInspectionMethods,
)
from src.modules.catalogue.application.use_cases.inspection_method.move_inspection_method import (
    MoveInspectionMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.move_inspection_method import (
    PlaceInspectionMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.restore_inspection_method import (
    RestoreInspectionMethod,
)
from src.modules.catalogue.application.use_cases.inspection_method.update_inspection_method import (
    UpdateInspectionMethod,
)
from src.modules.catalogue.application.use_cases.made_item.archive_made_item import ArchiveMadeItem
from src.modules.catalogue.application.use_cases.made_item.create_made_item import CreateMadeItem
from src.modules.catalogue.application.use_cases.made_item.create_made_item_process import (
    CreateMadeItemProcess,
)
from src.modules.catalogue.application.use_cases.made_item.create_made_item_revision import (
    CreateMadeItemRevision,
)
from src.modules.catalogue.application.use_cases.made_item.delete_made_item_file import (
    DeleteMadeItemFile,
)
from src.modules.catalogue.application.use_cases.made_item.delete_made_item_process import (
    DeleteMadeItemProcess,
)
from src.modules.catalogue.application.use_cases.made_item.download_made_item_file import (
    DownloadMadeItemFile,
)
from src.modules.catalogue.application.use_cases.made_item.get_made_item import GetMadeItem
from src.modules.catalogue.application.use_cases.made_item.get_made_item import GetMadeItems
from src.modules.catalogue.application.use_cases.made_item.get_made_item_files import (
    GetMadeItemFiles,
)
from src.modules.catalogue.application.use_cases.made_item.get_made_item_revisions import (
    GetMadeItemRevisions,
)
from src.modules.catalogue.application.use_cases.made_item.get_made_item_revisions_by_part_number import (
    GetMadeItemRevisionsByPartNumber,
)
from src.modules.catalogue.application.use_cases.made_item.list_made_item_merge_targets import (
    ListMadeItemMergeTargets,
)
from src.modules.catalogue.application.use_cases.made_item.merge_made_item import MergeMadeItem
from src.modules.catalogue.application.use_cases.made_item.regroup_made_item_processes import (
    RegroupMadeItemProcesses,
)
from src.modules.catalogue.application.use_cases.made_item.reorder_made_item_processes import (
    ReorderMadeItemProcesses,
)
from src.modules.catalogue.application.use_cases.made_item.restore_made_item import RestoreMadeItem
from src.modules.catalogue.application.use_cases.made_item.update_made_item import UpdateMadeItem
from src.modules.catalogue.application.use_cases.made_item.update_made_item_file import (
    UpdateMadeItemFile,
)
from src.modules.catalogue.application.use_cases.made_item.update_made_item_process import (
    UpdateMadeItemProcess,
)
from src.modules.catalogue.application.use_cases.made_item.upload_made_item_file import (
    UploadMadeItemFile,
)
from src.modules.catalogue.application.use_cases.product_family.archive_product_family import (
    ArchiveProductFamily,
)
from src.modules.catalogue.application.use_cases.product_family.create_product_family import (
    CreateProductFamily,
)
from src.modules.catalogue.application.use_cases.product_family.get_product_family import (
    GetProductFamilies,
)
from src.modules.catalogue.application.use_cases.product_family.get_product_family import (
    GetProductFamily,
)
from src.modules.catalogue.application.use_cases.product_family.move_product_family import (
    MoveProductFamily,
)
from src.modules.catalogue.application.use_cases.product_family.move_product_family import (
    PlaceProductFamily,
)
from src.modules.catalogue.application.use_cases.product_family.restore_product_family import (
    RestoreProductFamily,
)
from src.modules.catalogue.application.use_cases.product_family.update_product_family import (
    UpdateProductFamily,
)
from src.modules.catalogue.application.use_cases.source_item.archive_source_item import (
    ArchiveSourceItem,
)
from src.modules.catalogue.application.use_cases.source_item.create_source_item import (
    CreateSourceItem,
)
from src.modules.catalogue.application.use_cases.source_item.delete_source_item_file import (
    DeleteSourceItemFile,
)
from src.modules.catalogue.application.use_cases.source_item.download_source_item_file import (
    DownloadSourceItemFile,
)
from src.modules.catalogue.application.use_cases.source_item.get_source_item import GetSourceItem
from src.modules.catalogue.application.use_cases.source_item.get_source_item import GetSourceItems
from src.modules.catalogue.application.use_cases.source_item.get_source_item_files import (
    GetSourceItemFiles,
)
from src.modules.catalogue.application.use_cases.source_item.restore_source_item import (
    RestoreSourceItem,
)
from src.modules.catalogue.application.use_cases.source_item.update_source_item import (
    UpdateSourceItem,
)
from src.modules.catalogue.application.use_cases.source_item.update_source_item_file import (
    UpdateSourceItemFile,
)
from src.modules.catalogue.application.use_cases.source_item.upload_source_item_file import (
    UploadSourceItemFile,
)
from src.modules.catalogue.application.use_cases.source_item_type.archive_source_item_type import (
    ArchiveSourceItemType,
)
from src.modules.catalogue.application.use_cases.source_item_type.create_source_item_type import (
    CreateSourceItemType,
)
from src.modules.catalogue.application.use_cases.source_item_type.get_source_item_type import (
    GetSourceItemType,
)
from src.modules.catalogue.application.use_cases.source_item_type.get_source_item_type import (
    GetSourceItemTypes,
)
from src.modules.catalogue.application.use_cases.source_item_type.move_source_item_type import (
    MoveSourceItemType,
)
from src.modules.catalogue.application.use_cases.source_item_type.move_source_item_type import (
    PlaceSourceItemType,
)
from src.modules.catalogue.application.use_cases.source_item_type.restore_source_item_type import (
    RestoreSourceItemType,
)
from src.modules.catalogue.application.use_cases.source_item_type.update_source_item_type import (
    UpdateSourceItemType,
)
from src.modules.catalogue.ports.outbound.bought_item_usage_port import IBoughtItemUsages
from src.modules.catalogue.ports.outbound.cad_source_port import ICadSource
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.catalogue.ports.outbound.default_machine_port import IDefaultMachineLookup
from src.modules.catalogue.ports.outbound.inspection_method_usage_port import IInspectionMethodUsage
from src.modules.catalogue.ports.outbound.made_item_usage_port import IMadeItemUsages
from src.modules.catalogue.ports.outbound.repositories.article_group_repository import (
    IArticleGroupRepository,
)
from src.modules.catalogue.ports.outbound.repositories.bought_item_file_repository import (
    IBoughtItemFileRepository,
)
from src.modules.catalogue.ports.outbound.repositories.bought_item_repository import (
    IBoughtItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.customer_repository import (
    ICustomerRepository,
)
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    IFabricationMethodRepository,
)
from src.modules.catalogue.ports.outbound.repositories.inspection_method_repository import (
    IInspectionMethodRepository,
)
from src.modules.catalogue.ports.outbound.repositories.item_picture_repository import (
    IItemPictureRepository,
)
from src.modules.catalogue.ports.outbound.repositories.made_item_file_repository import (
    IMadeItemFileRepository,
)
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.part_number_registry import (
    IPartNumberRegistry,
)
from src.modules.catalogue.ports.outbound.repositories.product_family_repository import (
    IProductFamilyRepository,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_file_repository import (
    ISourceItemFileRepository,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    ISourceItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_type_repository import (
    ISourceItemTypeRepository,
)
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.platform.adapters.inbound.api.deps.bindings import get_linked_files
from src.modules.platform.adapters.inbound.api.deps.bindings import get_schedule_recompute
from src.modules.platform.adapters.inbound.api.deps.database import get_transactional_event_bus
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_storage_adapter
from src.modules.platform.application.services.file_attachments.base import ILinkedFiles
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_create_source_item_use_case(
    source_item_repo: ISourceItemRepository = Depends(get_source_item_repo),
    supplier_repo: ISupplierRepository = Depends(get_supplier_repo),
    source_item_type_repo: ISourceItemTypeRepository = Depends(get_source_item_type_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateSourceItem:
    return CreateSourceItem(
        source_item_repo=source_item_repo,
        supplier_repo=supplier_repo,
        source_item_type_repo=source_item_type_repo,
        uow=uow,
    )


def get_update_source_item_use_case(
    source_item_repo: ISourceItemRepository = Depends(get_source_item_repo),
    supplier_repo: ISupplierRepository = Depends(get_supplier_repo),
    source_item_type_repo: ISourceItemTypeRepository = Depends(get_source_item_type_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateSourceItem:
    return UpdateSourceItem(
        source_item_repo=source_item_repo,
        supplier_repo=supplier_repo,
        source_item_type_repo=source_item_type_repo,
        uow=uow,
        event_bus=event_bus,
    )


def get_source_item_use_case(
    source_item_repo: ISourceItemRepository = Depends(get_source_item_repo),
) -> GetSourceItem:
    return GetSourceItem(source_item_repo=source_item_repo)


def get_source_items_use_case(
    source_item_repo: ISourceItemRepository = Depends(get_source_item_repo),
) -> GetSourceItems:
    return GetSourceItems(source_item_repo=source_item_repo)


def get_archive_source_item_use_case(
    source_item_repo: ISourceItemRepository = Depends(get_source_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ArchiveSourceItem:
    return ArchiveSourceItem(source_item_repo=source_item_repo, uow=uow)


def get_restore_source_item_use_case(
    source_item_repo: ISourceItemRepository = Depends(get_source_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RestoreSourceItem:
    return RestoreSourceItem(source_item_repo=source_item_repo, uow=uow)


def get_create_source_item_type_use_case(
    source_item_type_repo: ISourceItemTypeRepository = Depends(get_source_item_type_repo),
    settings: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateSourceItemType:
    return CreateSourceItemType(
        source_item_type_repo=source_item_type_repo, settings=settings, uow=uow
    )


def get_update_source_item_type_use_case(
    source_item_type_repo: ISourceItemTypeRepository = Depends(get_source_item_type_repo),
    settings: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateSourceItemType:
    return UpdateSourceItemType(
        source_item_type_repo=source_item_type_repo, settings=settings, uow=uow
    )


def get_source_item_type_use_case(
    source_item_type_repo: ISourceItemTypeRepository = Depends(get_source_item_type_repo),
) -> GetSourceItemType:
    return GetSourceItemType(source_item_type_repo=source_item_type_repo)


def get_source_item_types_use_case(
    source_item_type_repo: ISourceItemTypeRepository = Depends(get_source_item_type_repo),
) -> GetSourceItemTypes:
    return GetSourceItemTypes(source_item_type_repo=source_item_type_repo)


def get_archive_source_item_type_use_case(
    source_item_type_repo: ISourceItemTypeRepository = Depends(get_source_item_type_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ArchiveSourceItemType:
    return ArchiveSourceItemType(source_item_type_repo=source_item_type_repo, uow=uow)


def get_restore_source_item_type_use_case(
    source_item_type_repo: ISourceItemTypeRepository = Depends(get_source_item_type_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RestoreSourceItemType:
    return RestoreSourceItemType(source_item_type_repo=source_item_type_repo, uow=uow)


def get_create_bought_item_use_case(
    bought_item_repo: IBoughtItemRepository = Depends(get_bought_item_repo),
    supplier_repo: ISupplierRepository = Depends(get_supplier_repo),
    article_group_repo: IArticleGroupRepository = Depends(get_article_group_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    part_number_registry: IPartNumberRegistry = Depends(get_part_number_registry_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    product_family_repo: IProductFamilyRepository = Depends(get_product_family_repo),
    cad_source: ICadSource = Depends(get_cad_source),
) -> CreateBoughtItem:
    return CreateBoughtItem(
        bought_item_repo=bought_item_repo,
        supplier_repo=supplier_repo,
        article_group_repo=article_group_repo,
        admin_settings_repo=admin_settings_repo,
        cad_source=cad_source,
        part_number_registry=part_number_registry,
        event_bus=event_bus,
        uow=uow,
        product_family_repo=product_family_repo,
    )


def get_update_bought_item_use_case(
    bought_item_repo: IBoughtItemRepository = Depends(get_bought_item_repo),
    supplier_repo: ISupplierRepository = Depends(get_supplier_repo),
    article_group_repo: IArticleGroupRepository = Depends(get_article_group_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    part_number_registry: IPartNumberRegistry = Depends(get_part_number_registry_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    product_family_repo: IProductFamilyRepository = Depends(get_product_family_repo),
    cad_source: ICadSource = Depends(get_cad_source),
) -> UpdateBoughtItem:
    return UpdateBoughtItem(
        bought_item_repo=bought_item_repo,
        supplier_repo=supplier_repo,
        article_group_repo=article_group_repo,
        admin_settings_repo=admin_settings_repo,
        cad_source=cad_source,
        part_number_registry=part_number_registry,
        uow=uow,
        product_family_repo=product_family_repo,
        event_bus=event_bus,
    )


def get_bought_item_use_case(
    bought_item_repo: IBoughtItemRepository = Depends(get_bought_item_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    cad_source: ICadSource = Depends(get_cad_source),
) -> GetBoughtItem:
    return GetBoughtItem(bought_item_repo=bought_item_repo, cad_source=cad_source)


def get_bought_items_use_case(
    bought_item_repo: IBoughtItemRepository = Depends(get_bought_item_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    cad_source: ICadSource = Depends(get_cad_source),
) -> GetBoughtItems:
    return GetBoughtItems(bought_item_repo=bought_item_repo, cad_source=cad_source)


def get_archive_bought_item_use_case(
    bought_item_repo: IBoughtItemRepository = Depends(get_bought_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ArchiveBoughtItem:
    return ArchiveBoughtItem(bought_item_repo=bought_item_repo, uow=uow)


def get_restore_bought_item_use_case(
    bought_item_repo: IBoughtItemRepository = Depends(get_bought_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RestoreBoughtItem:
    return RestoreBoughtItem(bought_item_repo=bought_item_repo, uow=uow)


def get_list_bought_item_merge_targets_use_case(
    bought_item_repo: IBoughtItemRepository = Depends(get_bought_item_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    cad_source: ICadSource = Depends(get_cad_source),
) -> ListBoughtItemMergeTargets:
    return ListBoughtItemMergeTargets(bought_item_repo=bought_item_repo, cad_source=cad_source)


def get_merge_bought_item_use_case(
    bought_item_repo: IBoughtItemRepository = Depends(get_bought_item_repo),
    file_repo: IBoughtItemFileRepository = Depends(get_bought_item_file_repo),
    picture_repo: IItemPictureRepository = Depends(get_item_picture_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    part_number_registry: IPartNumberRegistry = Depends(get_part_number_registry_repo),
    item_usages: IBoughtItemUsages = Depends(get_bought_item_usages),
    cad_source: ICadSource = Depends(get_cad_source),
) -> MergeBoughtItem:
    return MergeBoughtItem(
        item_usages=item_usages,
        item_repo=bought_item_repo,
        file_repo=file_repo,
        picture_repo=picture_repo,
        uow=uow,
        cad_source=cad_source,
        part_number_registry=part_number_registry,
    )


def get_bought_item_files_use_case(
    item_repo: IBoughtItemRepository = Depends(get_bought_item_repo),
    file_repo: IBoughtItemFileRepository = Depends(get_bought_item_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    pdm_document_link_repo: ILinkedFiles = Depends(get_linked_files),
) -> GetBoughtItemFiles:
    return GetBoughtItemFiles(
        item_repo=item_repo,
        file_repo=file_repo,
        storage=storage,
        pdm_document_link_repo=pdm_document_link_repo,
    )


def get_upload_bought_item_file_use_case(
    item_repo: IBoughtItemRepository = Depends(get_bought_item_repo),
    file_repo: IBoughtItemFileRepository = Depends(get_bought_item_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UploadBoughtItemFile:
    return UploadBoughtItemFile(item_repo=item_repo, file_repo=file_repo, storage=storage, uow=uow)


def get_update_bought_item_file_use_case(
    file_repo: IBoughtItemFileRepository = Depends(get_bought_item_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateBoughtItemFile:
    return UpdateBoughtItemFile(file_repo=file_repo, storage=storage, uow=uow)


def get_delete_bought_item_file_use_case(
    file_repo: IBoughtItemFileRepository = Depends(get_bought_item_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DeleteBoughtItemFile:
    return DeleteBoughtItemFile(file_repo=file_repo, storage=storage, uow=uow)


def get_download_bought_item_file_use_case(
    file_repo: IBoughtItemFileRepository = Depends(get_bought_item_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DownloadBoughtItemFile:
    return DownloadBoughtItemFile(file_repo=file_repo, storage=storage, uow=uow)


def get_create_made_item_use_case(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    article_group_repo: IArticleGroupRepository = Depends(get_article_group_repo),
    bought_item_repo: IBoughtItemRepository = Depends(get_bought_item_repo),
    source_item_repo: ISourceItemRepository = Depends(get_source_item_repo),
    fabrication_method_repo: IFabricationMethodRepository = Depends(get_fabrication_method_repo),
    inspection_method_repo: IInspectionMethodRepository = Depends(get_inspection_method_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    customer_repo: ICustomerRepository = Depends(get_customer_repo),
    part_number_registry: IPartNumberRegistry = Depends(get_part_number_registry_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    cad_source: ICadSource = Depends(get_cad_source),
) -> CreateMadeItem:
    return CreateMadeItem(
        made_item_repo=made_item_repo,
        article_group_repo=article_group_repo,
        bought_item_repo=bought_item_repo,
        source_item_repo=source_item_repo,
        fabrication_method_repo=fabrication_method_repo,
        inspection_method_repo=inspection_method_repo,
        admin_settings_repo=admin_settings_repo,
        cad_source=cad_source,
        customer_repo=customer_repo,
        part_number_registry=part_number_registry,
        event_bus=event_bus,
        uow=uow,
    )


def get_update_made_item_use_case(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    article_group_repo: IArticleGroupRepository = Depends(get_article_group_repo),
    bought_item_repo: IBoughtItemRepository = Depends(get_bought_item_repo),
    source_item_repo: ISourceItemRepository = Depends(get_source_item_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    customer_repo: ICustomerRepository = Depends(get_customer_repo),
    part_number_registry: IPartNumberRegistry = Depends(get_part_number_registry_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    cad_source: ICadSource = Depends(get_cad_source),
) -> UpdateMadeItem:
    return UpdateMadeItem(
        made_item_repo=made_item_repo,
        article_group_repo=article_group_repo,
        bought_item_repo=bought_item_repo,
        source_item_repo=source_item_repo,
        admin_settings_repo=admin_settings_repo,
        cad_source=cad_source,
        customer_repo=customer_repo,
        part_number_registry=part_number_registry,
        uow=uow,
        event_bus=event_bus,
    )


def get_create_made_item_revision_use_case(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    article_group_repo: IArticleGroupRepository = Depends(get_article_group_repo),
    bought_item_repo: IBoughtItemRepository = Depends(get_bought_item_repo),
    source_item_repo: ISourceItemRepository = Depends(get_source_item_repo),
    fabrication_method_repo: IFabricationMethodRepository = Depends(get_fabrication_method_repo),
    inspection_method_repo: IInspectionMethodRepository = Depends(get_inspection_method_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    customer_repo: ICustomerRepository = Depends(get_customer_repo),
    part_number_registry: IPartNumberRegistry = Depends(get_part_number_registry_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateMadeItemRevision:
    return CreateMadeItemRevision(
        made_item_repo=made_item_repo,
        article_group_repo=article_group_repo,
        bought_item_repo=bought_item_repo,
        source_item_repo=source_item_repo,
        fabrication_method_repo=fabrication_method_repo,
        inspection_method_repo=inspection_method_repo,
        admin_settings_repo=admin_settings_repo,
        customer_repo=customer_repo,
        part_number_registry=part_number_registry,
        event_bus=event_bus,
        uow=uow,
    )


def get_made_item_revisions_use_case(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
) -> GetMadeItemRevisions:
    return GetMadeItemRevisions(
        made_item_repo=made_item_repo, admin_settings_repo=admin_settings_repo
    )


def get_made_item_use_case(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    cad_source: ICadSource = Depends(get_cad_source),
) -> GetMadeItem:
    return GetMadeItem(made_item_repo=made_item_repo, cad_source=cad_source)


def get_made_items_use_case(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    cad_source: ICadSource = Depends(get_cad_source),
) -> GetMadeItems:
    return GetMadeItems(made_item_repo=made_item_repo, cad_source=cad_source)


def get_archive_made_item_use_case(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ArchiveMadeItem:
    return ArchiveMadeItem(made_item_repo=made_item_repo, uow=uow)


def get_restore_made_item_use_case(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RestoreMadeItem:
    return RestoreMadeItem(made_item_repo=made_item_repo, uow=uow)


def get_made_item_revisions_by_part_number_use_case(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
) -> GetMadeItemRevisionsByPartNumber:
    return GetMadeItemRevisionsByPartNumber(
        made_item_repo=made_item_repo, admin_settings_repo=admin_settings_repo
    )


def get_list_made_item_merge_targets_use_case(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    cad_source: ICadSource = Depends(get_cad_source),
) -> ListMadeItemMergeTargets:
    return ListMadeItemMergeTargets(made_item_repo=made_item_repo, cad_source=cad_source)


def get_merge_made_item_use_case(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    file_repo: IMadeItemFileRepository = Depends(get_made_item_file_repo),
    picture_repo: IItemPictureRepository = Depends(get_item_picture_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    part_number_registry: IPartNumberRegistry = Depends(get_part_number_registry_repo),
    item_usages: IMadeItemUsages = Depends(get_made_item_usages),
    cad_source: ICadSource = Depends(get_cad_source),
) -> MergeMadeItem:
    return MergeMadeItem(
        item_usages=item_usages,
        item_repo=made_item_repo,
        file_repo=file_repo,
        picture_repo=picture_repo,
        uow=uow,
        cad_source=cad_source,
        part_number_registry=part_number_registry,
    )


def get_create_made_item_process_use_case(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    fabrication_method_repo: IFabricationMethodRepository = Depends(get_fabrication_method_repo),
    inspection_method_repo: IInspectionMethodRepository = Depends(get_inspection_method_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateMadeItemProcess:
    return CreateMadeItemProcess(
        made_item_repo=made_item_repo,
        fabrication_method_repo=fabrication_method_repo,
        inspection_method_repo=inspection_method_repo,
        admin_settings_repo=admin_settings_repo,
        uow=uow,
    )


def get_update_made_item_process_use_case(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    fabrication_method_repo: IFabricationMethodRepository = Depends(get_fabrication_method_repo),
    inspection_method_repo: IInspectionMethodRepository = Depends(get_inspection_method_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateMadeItemProcess:
    return UpdateMadeItemProcess(
        made_item_repo=made_item_repo,
        fabrication_method_repo=fabrication_method_repo,
        inspection_method_repo=inspection_method_repo,
        admin_settings_repo=admin_settings_repo,
        uow=uow,
    )


def get_delete_made_item_process_use_case(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DeleteMadeItemProcess:
    return DeleteMadeItemProcess(
        made_item_repo=made_item_repo, admin_settings_repo=admin_settings_repo, uow=uow
    )


def get_reorder_made_item_processes_use_case(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ReorderMadeItemProcesses:
    return ReorderMadeItemProcesses(
        made_item_repo=made_item_repo,
        admin_settings_repo=admin_settings_repo,
        uow=uow,
    )


def get_regroup_made_item_processes_use_case(
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RegroupMadeItemProcesses:
    return RegroupMadeItemProcesses(
        made_item_repo=made_item_repo,
        admin_settings_repo=admin_settings_repo,
        uow=uow,
    )


def get_made_item_files_use_case(
    item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    file_repo: IMadeItemFileRepository = Depends(get_made_item_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    pdm_document_link_repo: ILinkedFiles = Depends(get_linked_files),
) -> GetMadeItemFiles:
    return GetMadeItemFiles(
        item_repo=item_repo,
        file_repo=file_repo,
        storage=storage,
        pdm_document_link_repo=pdm_document_link_repo,
    )


def get_upload_made_item_file_use_case(
    item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    file_repo: IMadeItemFileRepository = Depends(get_made_item_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UploadMadeItemFile:
    return UploadMadeItemFile(
        item_repo=item_repo,
        file_repo=file_repo,
        storage=storage,
        admin_settings_repo=admin_settings_repo,
        uow=uow,
    )


def get_update_made_item_file_use_case(
    file_repo: IMadeItemFileRepository = Depends(get_made_item_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateMadeItemFile:
    return UpdateMadeItemFile(
        file_repo=file_repo,
        storage=storage,
        made_item_repo=made_item_repo,
        admin_settings_repo=admin_settings_repo,
        uow=uow,
    )


def get_delete_made_item_file_use_case(
    file_repo: IMadeItemFileRepository = Depends(get_made_item_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    made_item_repo: IMadeItemRepository = Depends(get_made_item_repo),
    admin_settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DeleteMadeItemFile:
    return DeleteMadeItemFile(
        file_repo=file_repo,
        storage=storage,
        made_item_repo=made_item_repo,
        admin_settings_repo=admin_settings_repo,
        uow=uow,
    )


def get_download_made_item_file_use_case(
    file_repo: IMadeItemFileRepository = Depends(get_made_item_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DownloadMadeItemFile:
    return DownloadMadeItemFile(file_repo=file_repo, storage=storage, uow=uow)


def get_source_item_files_use_case(
    item_repo: ISourceItemRepository = Depends(get_source_item_repo),
    file_repo: ISourceItemFileRepository = Depends(get_source_item_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
) -> GetSourceItemFiles:
    return GetSourceItemFiles(item_repo=item_repo, file_repo=file_repo, storage=storage)


def get_upload_source_item_file_use_case(
    item_repo: ISourceItemRepository = Depends(get_source_item_repo),
    file_repo: ISourceItemFileRepository = Depends(get_source_item_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UploadSourceItemFile:
    return UploadSourceItemFile(item_repo=item_repo, file_repo=file_repo, storage=storage, uow=uow)


def get_update_source_item_file_use_case(
    file_repo: ISourceItemFileRepository = Depends(get_source_item_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateSourceItemFile:
    return UpdateSourceItemFile(file_repo=file_repo, storage=storage, uow=uow)


def get_delete_source_item_file_use_case(
    file_repo: ISourceItemFileRepository = Depends(get_source_item_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DeleteSourceItemFile:
    return DeleteSourceItemFile(file_repo=file_repo, storage=storage, uow=uow)


def get_download_source_item_file_use_case(
    file_repo: ISourceItemFileRepository = Depends(get_source_item_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DownloadSourceItemFile:
    return DownloadSourceItemFile(file_repo=file_repo, storage=storage, uow=uow)


def get_create_article_group_use_case(
    article_group_repo: IArticleGroupRepository = Depends(get_article_group_repo),
    settings: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateArticleGroup:
    return CreateArticleGroup(article_group_repo=article_group_repo, settings=settings, uow=uow)


def get_update_article_group_use_case(
    article_group_repo: IArticleGroupRepository = Depends(get_article_group_repo),
    settings: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateArticleGroup:
    return UpdateArticleGroup(article_group_repo=article_group_repo, settings=settings, uow=uow)


def get_article_group_use_case(
    article_group_repo: IArticleGroupRepository = Depends(get_article_group_repo),
) -> GetArticleGroup:
    return GetArticleGroup(article_group_repo=article_group_repo)


def get_article_groups_use_case(
    article_group_repo: IArticleGroupRepository = Depends(get_article_group_repo),
) -> GetArticleGroups:
    return GetArticleGroups(article_group_repo=article_group_repo)


def get_archive_article_group_use_case(
    article_group_repo: IArticleGroupRepository = Depends(get_article_group_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ArchiveArticleGroup:
    return ArchiveArticleGroup(article_group_repo=article_group_repo, uow=uow)


def get_restore_article_group_use_case(
    article_group_repo: IArticleGroupRepository = Depends(get_article_group_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RestoreArticleGroup:
    return RestoreArticleGroup(article_group_repo=article_group_repo, uow=uow)


def get_create_product_family_use_case(
    product_family_repo: IProductFamilyRepository = Depends(get_product_family_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateProductFamily:
    return CreateProductFamily(product_family_repo=product_family_repo, uow=uow)


def get_update_product_family_use_case(
    product_family_repo: IProductFamilyRepository = Depends(get_product_family_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateProductFamily:
    return UpdateProductFamily(product_family_repo=product_family_repo, uow=uow)


def get_product_family_use_case(
    product_family_repo: IProductFamilyRepository = Depends(get_product_family_repo),
) -> GetProductFamily:
    return GetProductFamily(product_family_repo=product_family_repo)


def get_product_families_use_case(
    product_family_repo: IProductFamilyRepository = Depends(get_product_family_repo),
) -> GetProductFamilies:
    return GetProductFamilies(product_family_repo=product_family_repo)


def get_archive_product_family_use_case(
    product_family_repo: IProductFamilyRepository = Depends(get_product_family_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ArchiveProductFamily:
    return ArchiveProductFamily(product_family_repo=product_family_repo, uow=uow)


def get_restore_product_family_use_case(
    product_family_repo: IProductFamilyRepository = Depends(get_product_family_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RestoreProductFamily:
    return RestoreProductFamily(product_family_repo=product_family_repo, uow=uow)


def get_create_fabrication_method_use_case(
    fabrication_method_repo: IFabricationMethodRepository = Depends(get_fabrication_method_repo),
    supplier_repo: ISupplierRepository = Depends(get_supplier_repo),
    settings: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateFabricationMethod:
    return CreateFabricationMethod(
        fabrication_method_repo=fabrication_method_repo,
        supplier_repo=supplier_repo,
        settings=settings,
        uow=uow,
    )


def get_update_fabrication_method_use_case(
    fabrication_method_repo: IFabricationMethodRepository = Depends(get_fabrication_method_repo),
    supplier_repo: ISupplierRepository = Depends(get_supplier_repo),
    settings: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: ScheduleRecompute = Depends(get_schedule_recompute),
) -> UpdateFabricationMethod:
    return UpdateFabricationMethod(
        fabrication_method_repo=fabrication_method_repo,
        supplier_repo=supplier_repo,
        settings=settings,
        uow=uow,
        recompute_schedule=recompute,
    )


def get_fabrication_method_use_case(
    fabrication_method_repo: IFabricationMethodRepository = Depends(get_fabrication_method_repo),
) -> GetFabricationMethod:
    return GetFabricationMethod(fabrication_method_repo=fabrication_method_repo)


def get_fabrication_methods_use_case(
    fabrication_method_repo: IFabricationMethodRepository = Depends(get_fabrication_method_repo),
) -> GetFabricationMethods:
    return GetFabricationMethods(fabrication_method_repo=fabrication_method_repo)


def get_assembly_default_fabrication_method_use_case(
    fabrication_method_repo: IFabricationMethodRepository = Depends(get_fabrication_method_repo),
) -> GetAssemblyDefaultFabricationMethod:
    return GetAssemblyDefaultFabricationMethod(fabrication_method_repo=fabrication_method_repo)


def get_archive_fabrication_method_use_case(
    fabrication_method_repo: IFabricationMethodRepository = Depends(get_fabrication_method_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ArchiveFabricationMethod:
    return ArchiveFabricationMethod(fabrication_method_repo=fabrication_method_repo, uow=uow)


def get_restore_fabrication_method_use_case(
    fabrication_method_repo: IFabricationMethodRepository = Depends(get_fabrication_method_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RestoreFabricationMethod:
    return RestoreFabricationMethod(fabrication_method_repo=fabrication_method_repo, uow=uow)


def get_create_inspection_method_use_case(
    inspection_method_repo: IInspectionMethodRepository = Depends(get_inspection_method_repo),
    machine_repo: IDefaultMachineLookup = Depends(get_default_machine_lookup),
    settings: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateInspectionMethod:
    return CreateInspectionMethod(
        inspection_method_repo=inspection_method_repo,
        machine_repo=machine_repo,
        settings=settings,
        uow=uow,
    )


def get_update_inspection_method_use_case(
    inspection_method_repo: IInspectionMethodRepository = Depends(get_inspection_method_repo),
    machine_repo: IDefaultMachineLookup = Depends(get_default_machine_lookup),
    settings: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateInspectionMethod:
    return UpdateInspectionMethod(
        inspection_method_repo=inspection_method_repo,
        machine_repo=machine_repo,
        settings=settings,
        uow=uow,
    )


def get_inspection_method_use_case(
    inspection_method_repo: IInspectionMethodRepository = Depends(get_inspection_method_repo),
) -> GetInspectionMethod:
    return GetInspectionMethod(inspection_method_repo=inspection_method_repo)


def get_inspection_methods_use_case(
    inspection_method_repo: IInspectionMethodRepository = Depends(get_inspection_method_repo),
) -> GetInspectionMethods:
    return GetInspectionMethods(inspection_method_repo=inspection_method_repo)


def get_archive_inspection_method_use_case(
    inspection_method_repo: IInspectionMethodRepository = Depends(get_inspection_method_repo),
    settings_repo: IInspectionMethodUsage = Depends(get_inspection_method_usage),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ArchiveInspectionMethod:
    return ArchiveInspectionMethod(
        inspection_method_repo=inspection_method_repo,
        settings_repo=settings_repo,
        uow=uow,
    )


def get_restore_inspection_method_use_case(
    inspection_method_repo: IInspectionMethodRepository = Depends(get_inspection_method_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RestoreInspectionMethod:
    return RestoreInspectionMethod(inspection_method_repo=inspection_method_repo, uow=uow)


def get_move_article_group_use_case(
    article_group_repo: IArticleGroupRepository = Depends(get_article_group_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> MoveArticleGroup:
    return MoveArticleGroup(article_group_repo=article_group_repo, uow=uow)


def get_move_source_item_type_use_case(
    source_item_type_repo: ISourceItemTypeRepository = Depends(get_source_item_type_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> MoveSourceItemType:
    return MoveSourceItemType(source_item_type_repo=source_item_type_repo, uow=uow)


def get_move_fabrication_method_use_case(
    fabrication_method_repo: IFabricationMethodRepository = Depends(get_fabrication_method_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> MoveFabricationMethod:
    return MoveFabricationMethod(fabrication_method_repo=fabrication_method_repo, uow=uow)


def get_move_inspection_method_use_case(
    inspection_method_repo: IInspectionMethodRepository = Depends(get_inspection_method_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> MoveInspectionMethod:
    return MoveInspectionMethod(inspection_method_repo=inspection_method_repo, uow=uow)


def get_move_product_family_use_case(
    product_family_repo: IProductFamilyRepository = Depends(get_product_family_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> MoveProductFamily:
    return MoveProductFamily(product_family_repo=product_family_repo, uow=uow)


def get_place_article_group_use_case(
    article_group_repo: IArticleGroupRepository = Depends(get_article_group_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> PlaceArticleGroup:
    return PlaceArticleGroup(article_group_repo=article_group_repo, uow=uow)


def get_place_fabrication_method_use_case(
    fabrication_method_repo: IFabricationMethodRepository = Depends(get_fabrication_method_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> PlaceFabricationMethod:
    return PlaceFabricationMethod(fabrication_method_repo=fabrication_method_repo, uow=uow)


def get_place_inspection_method_use_case(
    inspection_method_repo: IInspectionMethodRepository = Depends(get_inspection_method_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> PlaceInspectionMethod:
    return PlaceInspectionMethod(inspection_method_repo=inspection_method_repo, uow=uow)


def get_place_product_family_use_case(
    product_family_repo: IProductFamilyRepository = Depends(get_product_family_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> PlaceProductFamily:
    return PlaceProductFamily(product_family_repo=product_family_repo, uow=uow)


def get_place_source_item_type_use_case(
    source_item_type_repo: ISourceItemTypeRepository = Depends(get_source_item_type_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> PlaceSourceItemType:
    return PlaceSourceItemType(source_item_type_repo=source_item_type_repo, uow=uow)
