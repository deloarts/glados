"""
Takes a product repository, unlike its bought/made item counterparts:
ProductRules scopes update rights to the product, so the owning product has
to be resolved from the file before the permission check can run.
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.storage_asset import (
    delete_storage_object_best_effort,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.domain.errors import ProductFileNotFoundError
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.services.product_rules import ProductRules
from src.modules.workspace.ports.outbound.repositories.product_file_repository import (
    IProductFileRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository


class DeleteProductFile:
    def __init__(
        self,
        product_repo: IProductRepository,
        file_repo: IProductFileRepository,
        storage: IStoragePort | None,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._product_repo = product_repo
        self._file_repo = file_repo
        self._storage = storage
        self._uow = uow

    async def execute(self, actor: User, file_id: int) -> None:
        file = found_or_raise(
            await self._file_repo.get_by_id(file_id),
            ProductFileNotFoundError,
            f"File #{file_id} not found.",
        )

        product = found_or_raise(
            await self._product_repo.get_by_id(file.product_id),
            ProductNotFoundError,
            f"Product #{file.product_id} not found.",
        )

        ProductRules.assert_can_update(actor, product)

        await self._file_repo.delete(file)
        await self._uow.commit()

        # The blob goes only once the row deletion has committed, so a failed
        # commit leaves the row with its file intact. A failed blob delete
        # leaves an orphan, which is logged and not raised.
        if self._storage is not None:
            await delete_storage_object_best_effort(
                self._storage, file.storage_path, context=f"deleting product file #{file_id}"
            )
        log.info("Product file #%s (%r) deleted.", file_id, file.file_name)
