"""
File attachment endpoints for Product records.

Routes (all under /products/{product_id}/files):
  GET    /                  - list files (url=None when storage disabled)
  POST   /                  - upload file (multipart; requires storage)
  GET    /{file_id}         - download file bytes (same gate as list)
  PATCH  /{file_id}         - rename file (metadata only, no storage required)
  DELETE /{file_id}         - delete file and storage object

Its own module rather than routes on products.py, matching the bought/made
item file slices: these use cases need the storage adapter, which no other
product endpoint touches.
"""

from fastapi import Depends
from fastapi import Form
from fastapi import Response
from fastapi import UploadFile
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.download_headers import file_download_response
from src.modules.platform.adapters.inbound.api.download_headers import read_upload
from src.modules.platform.adapters.inbound.api.upload_limits import enforce_max_upload_size
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.adapters.inbound.api.deps.product_files import (
    get_delete_product_file_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_files import (
    get_download_product_file_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_files import get_product_files_use_case
from src.modules.workspace.adapters.inbound.api.deps.product_files import (
    get_update_product_file_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_files import (
    get_upload_product_file_use_case,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_file_schema import (
    ProductFileResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_file_schema import (
    ProductFileUpdateRequest,
)
from src.modules.workspace.application.dto.product_file_dto import ProductFileResult
from src.modules.workspace.application.dto.product_file_dto import UpdateProductFileCommand
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
from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory

router = APIRouter()


@router.get("/{product_id}/files", response_model=list[ProductFileResponse])
async def list_files(
    product_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetProductFiles = Depends(get_product_files_use_case),
) -> list[ProductFileResult]:
    return await use_case.execute(product_id=product_id)


@router.get("/{product_id}/files/{file_id}")
async def download_file(
    product_id: int,
    file_id: int,
    disposition: str = "attachment",
    _: User = Depends(get_current_active_user),
    use_case: DownloadProductFile = Depends(get_download_product_file_use_case),
) -> Response:
    """Stream the file's raw bytes. Gated identically to the list route
    above (login only), never the write gate."""
    file, data, content_type = await use_case.execute(product_id=product_id, file_id=file_id)
    return file_download_response(
        data, file.file_name, content_type=content_type, disposition=disposition
    )


@router.post(
    "/{product_id}/files",
    response_model=ProductFileResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_max_upload_size)],
)
async def upload_file(
    product_id: int,
    file: UploadFile,
    category: ProductFileCategory = Form(...),
    actor: User = Depends(get_current_active_user),
    use_case: UploadProductFile = Depends(get_upload_product_file_use_case),
) -> ProductFileResult:
    data, file_name, content_type = await read_upload(file)
    return await use_case.execute(
        actor=actor,
        product_id=product_id,
        data=data,
        file_name=file_name,
        content_type=content_type,
        category=category,
    )


@router.patch("/{product_id}/files/{file_id}", response_model=ProductFileResponse)
async def update_file(
    product_id: int,
    file_id: int,
    body: ProductFileUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateProductFile = Depends(get_update_product_file_use_case),
) -> ProductFileResult:
    return await use_case.execute(
        actor=actor,
        file_id=file_id,
        command=UpdateProductFileCommand(file_name=body.file_name),
    )


@router.delete("/{product_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    product_id: int,
    file_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteProductFile = Depends(get_delete_product_file_use_case),
) -> None:
    await use_case.execute(actor=actor, file_id=file_id)
