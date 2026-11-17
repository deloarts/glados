"""Use case factories: the bought item spreadsheet import and the EPLAN Data
Portal lookups."""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.items import get_create_bought_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_update_bought_item_use_case
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_article_group_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_bought_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_product_family_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_supplier_repo
from src.modules.catalogue.application.facade.item_commands import CreateBoughtItem
from src.modules.catalogue.application.facade.item_commands import UpdateBoughtItem
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.catalogue_queries import IArticleGroupQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IProductFamilyQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.external_data.adapters.inbound.api.deps.repositories import (
    get_external_data_settings_repo,
)
from src.modules.external_data.adapters.inbound.api.deps.services import (
    get_eplan_data_portal_factory,
)
from src.modules.external_data.application.use_cases.bought_item_import.batch_create_items import (
    CommitBatchBoughtItemRows,
)
from src.modules.external_data.application.use_cases.bought_item_import.batch_create_items import (
    ValidateBatchBoughtItemRows,
)
from src.modules.external_data.application.use_cases.eplan_data_portal.edp_lookup import (
    ApplyEdpLookup,
)
from src.modules.external_data.application.use_cases.eplan_data_portal.edp_lookup import (
    GetEdpAvailability,
)
from src.modules.external_data.application.use_cases.eplan_data_portal.edp_lookup import (
    GetEdpPartPicture,
)
from src.modules.external_data.application.use_cases.eplan_data_portal.edp_lookup import (
    LookupBoughtItemInEdp,
)
from src.modules.external_data.application.use_cases.eplan_data_portal.edp_lookup import (
    MatchEdpParts,
)
from src.modules.external_data.application.use_cases.eplan_data_portal.edp_lookup import (
    SearchEdpParts,
)
from src.modules.external_data.ports.outbound.eplan_data_portal_port import IEplanDataPortalFactory
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_transactional_event_bus
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_validate_batch_bought_items_use_case(
    bought_item_repo: IBoughtItemCadStore = Depends(get_bought_item_repo),
    supplier_repo: ISupplierQueries = Depends(get_supplier_repo),
    article_group_repo: IArticleGroupQueries = Depends(get_article_group_repo),
    admin_settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    product_family_repo: IProductFamilyQueries = Depends(get_product_family_repo),
    portal_factory: IEplanDataPortalFactory = Depends(get_eplan_data_portal_factory),
    create_item: CreateBoughtItem = Depends(get_create_bought_item_use_case),
) -> ValidateBatchBoughtItemRows:
    return ValidateBatchBoughtItemRows(
        bought_item_repo,
        supplier_repo,
        article_group_repo,
        product_family_repo,
        admin_settings_repo,
        event_bus=event_bus,
        portal_factory=portal_factory,
        create_item=create_item,
    )


def get_commit_batch_bought_items_use_case(
    bought_item_repo: IBoughtItemCadStore = Depends(get_bought_item_repo),
    supplier_repo: ISupplierQueries = Depends(get_supplier_repo),
    article_group_repo: IArticleGroupQueries = Depends(get_article_group_repo),
    admin_settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    product_family_repo: IProductFamilyQueries = Depends(get_product_family_repo),
    portal_factory: IEplanDataPortalFactory = Depends(get_eplan_data_portal_factory),
    create_item: CreateBoughtItem = Depends(get_create_bought_item_use_case),
) -> CommitBatchBoughtItemRows:
    return CommitBatchBoughtItemRows(
        bought_item_repo,
        supplier_repo,
        article_group_repo,
        product_family_repo,
        admin_settings_repo,
        event_bus=event_bus,
        portal_factory=portal_factory,
        create_item=create_item,
        uow=uow,
    )


def get_search_edp_parts_use_case(
    bought_item_repo: IBoughtItemCadStore = Depends(get_bought_item_repo),
    supplier_repo: ISupplierQueries = Depends(get_supplier_repo),
    product_family_repo: IProductFamilyQueries = Depends(get_product_family_repo),
    admin_settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    portal_factory: IEplanDataPortalFactory = Depends(get_eplan_data_portal_factory),
) -> SearchEdpParts:
    return SearchEdpParts(
        bought_item_repo, supplier_repo, product_family_repo, admin_settings_repo, portal_factory
    )


def get_match_edp_parts_use_case(
    bought_item_repo: IBoughtItemCadStore = Depends(get_bought_item_repo),
    supplier_repo: ISupplierQueries = Depends(get_supplier_repo),
    product_family_repo: IProductFamilyQueries = Depends(get_product_family_repo),
    admin_settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    portal_factory: IEplanDataPortalFactory = Depends(get_eplan_data_portal_factory),
) -> MatchEdpParts:
    return MatchEdpParts(
        bought_item_repo, supplier_repo, product_family_repo, admin_settings_repo, portal_factory
    )


def get_edp_availability_use_case(
    admin_settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
) -> GetEdpAvailability:
    return GetEdpAvailability(admin_settings_repo)


def get_edp_part_picture_use_case(
    bought_item_repo: IBoughtItemCadStore = Depends(get_bought_item_repo),
    supplier_repo: ISupplierQueries = Depends(get_supplier_repo),
    product_family_repo: IProductFamilyQueries = Depends(get_product_family_repo),
    admin_settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    portal_factory: IEplanDataPortalFactory = Depends(get_eplan_data_portal_factory),
) -> GetEdpPartPicture:
    return GetEdpPartPicture(
        bought_item_repo, supplier_repo, product_family_repo, admin_settings_repo, portal_factory
    )


def get_lookup_bought_item_in_edp_use_case(
    bought_item_repo: IBoughtItemCadStore = Depends(get_bought_item_repo),
    supplier_repo: ISupplierQueries = Depends(get_supplier_repo),
    product_family_repo: IProductFamilyQueries = Depends(get_product_family_repo),
    admin_settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    portal_factory: IEplanDataPortalFactory = Depends(get_eplan_data_portal_factory),
) -> LookupBoughtItemInEdp:
    return LookupBoughtItemInEdp(
        bought_item_repo, supplier_repo, product_family_repo, admin_settings_repo, portal_factory
    )


def get_apply_edp_lookup_use_case(
    bought_item_repo: IBoughtItemCadStore = Depends(get_bought_item_repo),
    supplier_repo: ISupplierQueries = Depends(get_supplier_repo),
    product_family_repo: IProductFamilyQueries = Depends(get_product_family_repo),
    admin_settings_repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    portal_factory: IEplanDataPortalFactory = Depends(get_eplan_data_portal_factory),
    update_item: UpdateBoughtItem = Depends(get_update_bought_item_use_case),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ApplyEdpLookup:
    return ApplyEdpLookup(
        bought_item_repo,
        supplier_repo,
        product_family_repo,
        admin_settings_repo,
        portal_factory,
        update_item=update_item,
        event_bus=event_bus,
        uow=uow,
    )
