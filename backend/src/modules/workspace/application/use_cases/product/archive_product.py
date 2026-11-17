"""
Archives a product (sets archived=True, is_active=False). Idempotent:
archiving an already-archived product is not an error.
"""

from src.modules.platform.application.services.archive_restore import set_archived
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.product_dto import ProductResult
from src.modules.workspace.application.mappers.product_mapper import ProductMapper
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.services.product_rules import ProductRules
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository


class ArchiveProduct:
    def __init__(
        self,
        product_repo: IProductRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._products = product_repo
        self._uow = uow

    async def execute(self, actor: User, product_id: int) -> ProductResult:
        ProductRules.assert_can_archive(actor)

        async def _before_save(product: Product) -> None:
            product.is_active = False

        saved = await set_archived(
            entity_id=product_id,
            archived=True,
            load=self._products.get_by_id,
            not_found=lambda pid: ProductNotFoundError(f"Product #{pid} not found."),
            save=self._products.save,
            before_save=_before_save,
        )
        await self._uow.commit()

        log.info(f"Archived product {saved.product_number!r} (ID={saved.id}).")

        return ProductMapper.to_result(saved)
