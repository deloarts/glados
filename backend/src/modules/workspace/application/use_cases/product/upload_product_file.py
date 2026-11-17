"""
Uploads a thumbnail, reference image or specification PDF to a product on
the shared item-file upload core.

Note the deviation from the other file uploads: ProductRules scopes update
rights to the product (manage:projects OR being its designated user), so the
product must be loaded before the permission check rather than after it.
"""

from src.modules.platform.application.services.file_attachments.base import UploadItemFileBase
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import StorageNotEnabledError
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.product_file_dto import ProductFileResult
from src.modules.workspace.application.use_cases.product._file_kind import PRODUCT_FILE_KIND
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.entities.product_file import ProductFile
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.services.product_rules import ProductRules
from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory
from src.modules.workspace.ports.outbound.repositories.product_file_repository import (
    IProductFileRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository


class UploadProductFile(UploadItemFileBase[ProductFile, ProductFileResult]):
    _kind = PRODUCT_FILE_KIND

    def __init__(
        self,
        product_repo: IProductRepository,
        file_repo: IProductFileRepository,
        storage: IStoragePort | None,
        *,
        uow: IUnitOfWork,
    ) -> None:
        super().__init__(product_repo, file_repo, storage, uow=uow)
        # The base keeps the parent repository at its minimal structural type;
        # ProductRules needs a typed Product, so keep the full port here too.
        self._product_repo = product_repo

    async def _load_writable_item(self, actor: User, item_id: int) -> Product:
        # Loaded before the permission check because the rule is scoped to the
        # product; see the module docstring.
        product = found_or_raise(
            await self._product_repo.get_by_id(item_id),
            ProductNotFoundError,
            f"Product #{item_id} not found.",
        )

        # A file is part of the product's editable state, so attaching one
        # requires the same rights as editing the product itself.
        ProductRules.assert_can_update(actor, product)

        if self._storage is None:
            raise StorageNotEnabledError("Storage is not enabled.")
        return product

    async def execute(
        self,
        actor: User,
        product_id: int,
        data: bytes,
        file_name: str,
        content_type: str,
        category: ProductFileCategory,
    ) -> ProductFileResult:
        return await super().execute(actor, product_id, data, file_name, content_type, category)
