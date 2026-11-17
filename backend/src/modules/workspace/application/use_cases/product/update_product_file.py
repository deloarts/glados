"""
Metadata-only update (file_name). Replacing file bytes requires DELETE + POST.

Takes a product repository, unlike its bought/made item counterparts:
ProductRules scopes update rights to the product, so the owning product has
to be resolved from the file before the permission check can run.
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.storage_asset import get_storage_url_best_effort
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.product_file_dto import ProductFileResult
from src.modules.workspace.application.dto.product_file_dto import UpdateProductFileCommand
from src.modules.workspace.domain.errors import ProductFileNotFoundError
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.services.product_rules import ProductRules
from src.modules.workspace.ports.outbound.repositories.product_file_repository import (
    IProductFileRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository


class UpdateProductFile:
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

    async def execute(
        self, actor: User, file_id: int, command: UpdateProductFileCommand
    ) -> ProductFileResult:
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

        file.file_name = command.file_name
        saved = await self._file_repo.save(file)
        await self._uow.commit()
        log.info("Product file #%s renamed to %r.", file_id, command.file_name)

        url = (
            get_storage_url_best_effort(
                self._storage,
                saved.storage_path,
                context=f"product file #{saved.id}",
                file_name=saved.file_name,
            )
            if self._storage is not None
            else None
        )

        return ProductFileResult(
            id=saved.id,
            public_id=saved.public_id,
            product_id=saved.product_id,
            file_name=saved.file_name,
            stored_name=saved.stored_name,
            mime_type=saved.mime_type,
            size_bytes=saved.size_bytes,
            storage_path=saved.storage_path,
            sha256=saved.sha256,
            category=saved.category,
            created=saved.created,
            uploaded_by_user_id=saved.uploaded_by_user_id,
            url=url,
        )
