"""Use case factory: GET /pat/lookups."""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_article_group_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_customer_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_fabrication_method_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_inspection_method_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_source_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_source_item_type_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_supplier_repo
from src.modules.catalogue.application.use_cases.lookups.get_lookups import GetLookups
from src.modules.catalogue.ports.outbound.repositories.article_group_repository import (
    IArticleGroupRepository,
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
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    ISourceItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_type_repository import (
    ISourceItemTypeRepository,
)
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)


def get_lookups_use_case(
    supplier_repo: ISupplierRepository = Depends(get_supplier_repo),
    article_group_repo: IArticleGroupRepository = Depends(get_article_group_repo),
    fabrication_method_repo: IFabricationMethodRepository = Depends(get_fabrication_method_repo),
    inspection_method_repo: IInspectionMethodRepository = Depends(get_inspection_method_repo),
    source_item_type_repo: ISourceItemTypeRepository = Depends(get_source_item_type_repo),
    source_item_repo: ISourceItemRepository = Depends(get_source_item_repo),
    customer_repo: ICustomerRepository = Depends(get_customer_repo),
) -> GetLookups:
    return GetLookups(
        supplier_repo=supplier_repo,
        article_group_repo=article_group_repo,
        fabrication_method_repo=fabrication_method_repo,
        inspection_method_repo=inspection_method_repo,
        source_item_type_repo=source_item_type_repo,
        source_item_repo=source_item_repo,
        customer_repo=customer_repo,
    )
