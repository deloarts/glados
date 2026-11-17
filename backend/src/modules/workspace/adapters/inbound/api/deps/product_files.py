"""Use case factories: the files of a product."""

from fastapi import Depends

from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_storage_adapter
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_file_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_repo
from src.modules.workspace.application.use_cases.product.delete_product_file import (
    DeleteProductFile,
)
from src.modules.workspace.application.use_cases.product.download_product_file import (
    DownloadProductFile,
)
from src.modules.workspace.application.use_cases.product.get_product_files import GetProductFiles
from src.modules.workspace.application.use_cases.product.update_product_file import (
    UpdateProductFile,
)
from src.modules.workspace.application.use_cases.product.upload_product_file import (
    UploadProductFile,
)
from src.modules.workspace.ports.outbound.repositories.product_file_repository import (
    IProductFileRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository

# Product file use cases take the product repository even where their
# bought/made item counterparts do not: ProductRules scopes update rights to
# the product, so the owning product has to be resolved before the check.


def get_product_files_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    file_repo: IProductFileRepository = Depends(get_product_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
) -> GetProductFiles:
    return GetProductFiles(product_repo=product_repo, file_repo=file_repo, storage=storage)


def get_upload_product_file_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    file_repo: IProductFileRepository = Depends(get_product_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UploadProductFile:
    return UploadProductFile(
        product_repo=product_repo, file_repo=file_repo, storage=storage, uow=uow
    )


def get_update_product_file_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    file_repo: IProductFileRepository = Depends(get_product_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateProductFile:
    return UpdateProductFile(
        product_repo=product_repo, file_repo=file_repo, storage=storage, uow=uow
    )


def get_delete_product_file_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    file_repo: IProductFileRepository = Depends(get_product_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DeleteProductFile:
    return DeleteProductFile(
        product_repo=product_repo, file_repo=file_repo, storage=storage, uow=uow
    )


def get_download_product_file_use_case(
    file_repo: IProductFileRepository = Depends(get_product_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DownloadProductFile:
    return DownloadProductFile(file_repo=file_repo, storage=storage, uow=uow)
