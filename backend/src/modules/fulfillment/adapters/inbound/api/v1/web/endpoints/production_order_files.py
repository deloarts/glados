"""
Evidence file attachment endpoints for ProductionOrder QA/inspection
completions (routes (all under /production-orders/{order_id}/files):
  GET    /                  - list files (url=None when storage disabled)
  POST   /                  - upload file (multipart; requires storage)
  GET    /{file_id}         - download file bytes (same gate as list)
  PATCH  /{file_id}         - rename file (metadata only, no storage required)
  DELETE /{file_id}         - delete file and storage object

Every route requires write:inspections (checked inside the use cases, not
here, so it applies the same way regardless of caller).
"""

from fastapi import Depends
from fastapi import Form
from fastapi import Response
from fastapi import UploadFile
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_delete_production_order_file_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_download_production_order_file_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_production_order_files_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_update_production_order_file_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_upload_production_order_file_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_file_schema import (
    ProductionOrderFileResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_file_schema import (
    ProductionOrderFileUpdateRequest,
)
from src.modules.fulfillment.application.dto.production_order_file_dto import (
    ProductionOrderFileResult,
)
from src.modules.fulfillment.application.dto.production_order_file_dto import (
    UpdateProductionOrderFileCommand,
)
from src.modules.fulfillment.application.use_cases.production_order.delete_production_order_file import (
    DeleteProductionOrderFile,
)
from src.modules.fulfillment.application.use_cases.production_order.download_production_order_file import (
    DownloadProductionOrderFile,
)
from src.modules.fulfillment.application.use_cases.production_order.get_production_order_files import (
    GetProductionOrderFiles,
)
from src.modules.fulfillment.application.use_cases.production_order.update_production_order_file import (
    UpdateProductionOrderFile,
)
from src.modules.fulfillment.application.use_cases.production_order.upload_production_order_file import (
    UploadProductionOrderFile,
)
from src.modules.fulfillment.domain.value_objects.production_order_file_category import (
    ProductionOrderFileCategory,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.download_headers import file_download_response
from src.modules.platform.adapters.inbound.api.download_headers import read_upload
from src.modules.platform.adapters.inbound.api.upload_limits import enforce_max_upload_size
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/{order_id}/files", response_model=list[ProductionOrderFileResponse])
async def list_files(
    order_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetProductionOrderFiles = Depends(get_production_order_files_use_case),
) -> list[ProductionOrderFileResult]:
    return await use_case.execute(actor=actor, order_id=order_id)


@router.get("/{order_id}/files/{file_id}")
async def download_file(
    order_id: int,
    file_id: int,
    disposition: str = "attachment",
    actor: User = Depends(get_current_active_user),
    use_case: DownloadProductionOrderFile = Depends(get_download_production_order_file_use_case),
) -> Response:
    """Stream the file's raw bytes. Gated identically to the list route
    above (write:inspections)."""
    file, data, content_type = await use_case.execute(
        actor=actor, order_id=order_id, file_id=file_id
    )
    return file_download_response(
        data, file.file_name, content_type=content_type, disposition=disposition
    )


@router.post(
    "/{order_id}/files",
    response_model=ProductionOrderFileResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_max_upload_size)],
)
async def upload_file(
    order_id: int,
    file: UploadFile,
    category: ProductionOrderFileCategory = Form(...),
    actor: User = Depends(get_current_active_user),
    use_case: UploadProductionOrderFile = Depends(get_upload_production_order_file_use_case),
) -> ProductionOrderFileResult:
    data, file_name, content_type = await read_upload(file)
    return await use_case.execute(
        actor=actor,
        order_id=order_id,
        data=data,
        file_name=file_name,
        content_type=content_type,
        category=category,
    )


@router.patch("/{order_id}/files/{file_id}", response_model=ProductionOrderFileResponse)
async def update_file(
    order_id: int,
    file_id: int,
    body: ProductionOrderFileUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateProductionOrderFile = Depends(get_update_production_order_file_use_case),
) -> ProductionOrderFileResult:
    return await use_case.execute(
        actor=actor,
        file_id=file_id,
        command=UpdateProductionOrderFileCommand(file_name=body.file_name),
    )


@router.delete("/{order_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    order_id: int,
    file_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteProductionOrderFile = Depends(get_delete_production_order_file_use_case),
) -> None:
    await use_case.execute(actor=actor, file_id=file_id)
