"""Repository factories on the request's session, and the module's settings
store."""

from collections.abc import Callable

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
from src.modules.catalogue.adapters.outbound.persistence.repositories.catalogue_settings_repository import (
    SqlAlchemyCatalogueSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.contact_repository import (
    SqlAlchemyContactRepository,
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
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.part_number_registry_repository import (
    SqlAlchemyPartNumberRegistryRepository,
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
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.catalogue.ports.outbound.repositories.article_group_repository import (
    IArticleGroupRepository,
)
from src.modules.catalogue.ports.outbound.repositories.bought_item_file_repository import (
    IBoughtItemFileRepository,
)
from src.modules.catalogue.ports.outbound.repositories.bought_item_repository import (
    IBoughtItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.contact_repository import IContactRepository
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
from src.modules.platform.adapters.inbound.api.deps.database import repo_factory

get_contact_repo: Callable[[AsyncSession], IContactRepository] = repo_factory(
    SqlAlchemyContactRepository
)
get_customer_repo: Callable[[AsyncSession], ICustomerRepository] = repo_factory(
    SqlAlchemyCustomerRepository
)
get_bought_item_repo: Callable[[AsyncSession], IBoughtItemRepository] = repo_factory(
    SqlAlchemyBoughtItemRepository
)
get_source_item_repo: Callable[[AsyncSession], ISourceItemRepository] = repo_factory(
    SqlAlchemySourceItemRepository
)
get_source_item_file_repo: Callable[[AsyncSession], ISourceItemFileRepository] = repo_factory(
    SqlAlchemySourceItemFileRepository
)
get_source_item_type_repo: Callable[[AsyncSession], ISourceItemTypeRepository] = repo_factory(
    SqlAlchemySourceItemTypeRepository
)
get_bought_item_file_repo: Callable[[AsyncSession], IBoughtItemFileRepository] = repo_factory(
    SqlAlchemyBoughtItemFileRepository
)
get_item_picture_repo: Callable[[AsyncSession], IItemPictureRepository] = repo_factory(
    SqlAlchemyItemPictureRepository
)
get_made_item_repo: Callable[[AsyncSession], IMadeItemRepository] = repo_factory(
    SqlAlchemyMadeItemRepository
)
get_made_item_file_repo: Callable[[AsyncSession], IMadeItemFileRepository] = repo_factory(
    SqlAlchemyMadeItemFileRepository
)
get_part_number_registry_repo: Callable[[AsyncSession], IPartNumberRegistry] = repo_factory(
    SqlAlchemyPartNumberRegistryRepository
)
get_supplier_repo: Callable[[AsyncSession], ISupplierRepository] = repo_factory(
    SqlAlchemySupplierRepository
)
get_article_group_repo: Callable[[AsyncSession], IArticleGroupRepository] = repo_factory(
    SqlAlchemyArticleGroupRepository
)
get_product_family_repo: Callable[[AsyncSession], IProductFamilyRepository] = repo_factory(
    SqlAlchemyProductFamilyRepository
)
get_fabrication_method_repo: Callable[[AsyncSession], IFabricationMethodRepository] = repo_factory(
    SqlAlchemyFabricationMethodRepository
)
get_inspection_method_repo: Callable[[AsyncSession], IInspectionMethodRepository] = repo_factory(
    SqlAlchemyInspectionMethodRepository
)

get_catalogue_settings_repo: Callable[[AsyncSession], ICatalogueSettingsRepository] = repo_factory(
    SqlAlchemyCatalogueSettingsRepository
)
