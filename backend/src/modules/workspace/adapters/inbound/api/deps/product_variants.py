"""Use case factories: the variants of a product."""

from fastapi import Depends

from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_variant_repo
from src.modules.workspace.application.use_cases.product_variant.variants import GetProductVariants
from src.modules.workspace.application.use_cases.product_variant.variants import SaveProductVariants
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository
from src.modules.workspace.ports.outbound.repositories.product_variant_repository import (
    IProductVariantRepository,
)


def get_product_variants_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    variant_repo: IProductVariantRepository = Depends(get_product_variant_repo),
) -> GetProductVariants:
    return GetProductVariants(product_repo=product_repo, variant_repo=variant_repo)


def get_save_product_variants_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    variant_repo: IProductVariantRepository = Depends(get_product_variant_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SaveProductVariants:
    return SaveProductVariants(product_repo=product_repo, variant_repo=variant_repo, uow=uow)
