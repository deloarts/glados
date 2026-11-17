"""
Reads and saves a product's variants as one ordered list. Reading needs an
active user, like reading the product; saving needs the rights to edit the
product (see ProductDeviceRules), and a variant taken out of the list is
archived so sequences that name it keep resolving it.
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.product_variant_dto import ProductVariantResult
from src.modules.workspace.application.dto.product_variant_dto import SaveProductVariantsCommand
from src.modules.workspace.domain.entities.product_variant import ProductVariant
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.policies.product_device_rules import ProductDeviceRules
from src.modules.workspace.domain.services.product_variant_rules import VariantDraft
from src.modules.workspace.domain.services.product_variant_rules import sync_variants
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository
from src.modules.workspace.ports.outbound.repositories.product_variant_repository import (
    IProductVariantRepository,
)


def _to_result(variant: ProductVariant) -> ProductVariantResult:
    return ProductVariantResult(
        id=variant.id,
        public_id=variant.public_id,
        product_id=variant.product_id,
        name=variant.name,
        sort_order=variant.sort_order,
        archived=variant.archived,
    )


class GetProductVariants:
    def __init__(
        self, product_repo: IProductRepository, variant_repo: IProductVariantRepository
    ) -> None:
        self._products = product_repo
        self._variants = variant_repo

    async def execute(self, product_id: int, include_archived: bool) -> list[ProductVariantResult]:
        found_or_raise(
            await self._products.get_by_id(product_id),
            ProductNotFoundError,
            f"Product #{product_id} not found.",
        )
        variants = await self._variants.get_by_product(product_id, include_archived)
        return [_to_result(v) for v in variants]


class SaveProductVariants:
    def __init__(
        self,
        product_repo: IProductRepository,
        variant_repo: IProductVariantRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._products = product_repo
        self._variants = variant_repo
        self._uow = uow

    async def execute(
        self, actor: User, product_id: int, cmd: SaveProductVariantsCommand
    ) -> list[ProductVariantResult]:
        product = found_or_raise(
            await self._products.get_by_id(product_id),
            ProductNotFoundError,
            f"Product #{product_id} not found.",
        )
        ProductDeviceRules.assert_can_edit(actor, product)
        existing = await self._variants.get_by_product(product_id, include_archived=True)
        variants = sync_variants(
            product_id, existing, [VariantDraft(d.id, d.name) for d in cmd.variants]
        )
        saved = await self._variants.save_all(product_id, variants)
        await self._uow.commit()
        log.info(f"Saved {len(cmd.variants)} variants of product #{product_id}.")
        return [_to_result(v) for v in saved if not v.archived]
