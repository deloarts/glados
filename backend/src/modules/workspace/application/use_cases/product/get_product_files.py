"""
Lists the files attached to a product on the shared item-file core. File
metadata is returned even when storage is disabled, with `url` set to None.
"""

from src.modules.platform.application.services.file_attachments.base import GetItemFilesBase
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.workspace.application.dto.product_file_dto import ProductFileResult
from src.modules.workspace.application.use_cases.product._file_kind import PRODUCT_FILE_KIND
from src.modules.workspace.domain.entities.product_file import ProductFile
from src.modules.workspace.ports.outbound.repositories.product_file_repository import (
    IProductFileRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository


class GetProductFiles(GetItemFilesBase[ProductFile, ProductFileResult]):
    _kind = PRODUCT_FILE_KIND

    def __init__(
        self,
        product_repo: IProductRepository,
        file_repo: IProductFileRepository,
        storage: IStoragePort | None,
    ) -> None:
        super().__init__(product_repo, file_repo, storage)

    async def execute(self, product_id: int) -> list[ProductFileResult]:
        return await super().execute(product_id)
