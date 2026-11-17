"""
File attachment endpoints for Order records.

Routes (all under /orders/{order_id}/files):
  GET    /                  - list files (url=None when storage disabled)
  POST   /                  - upload PDF (multipart; requires storage)
  GET    /{file_id}         - download file bytes (same gate as list)
  DELETE /{file_id}         - delete file and storage object

and /orders/{order_id}/items/{order_item_id}/deliveries/{delivery_id}/pictures:
  POST   /                  - upload a picture of one delivery row
"""

from fastapi import Depends
from fastapi import Form
from fastapi import Response
from fastapi import UploadFile
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_delete_order_file_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import (
    get_download_order_file_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_order_files_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import (
    get_upload_delivery_picture_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_upload_order_file_use_case
from src.modules.fulfillment.adapters.inbound.api.schemas.order_file_schema import OrderFileResponse
from src.modules.fulfillment.application.dto.order_file_dto import OrderFileResult
from src.modules.fulfillment.application.use_cases.order.delete_order_file import DeleteOrderFile
from src.modules.fulfillment.application.use_cases.order.download_order_file import (
    DownloadOrderFile,
)
from src.modules.fulfillment.application.use_cases.order.get_order_files import GetOrderFiles
from src.modules.fulfillment.application.use_cases.order.upload_delivery_picture import (
    UploadDeliveryPicture,
)
from src.modules.fulfillment.application.use_cases.order.upload_order_file import UploadOrderFile
from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.download_headers import file_download_response
from src.modules.platform.adapters.inbound.api.download_headers import read_upload
from src.modules.platform.adapters.inbound.api.upload_limits import enforce_max_upload_size
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/{order_id}/files", response_model=list[OrderFileResponse])
async def list_order_files(
    order_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetOrderFiles = Depends(get_order_files_use_case),
) -> list[OrderFileResult]:
    return await use_case.execute(order_id=order_id)


@router.get("/{order_id}/files/{file_id}")
async def download_order_file(
    order_id: int,
    file_id: int,
    disposition: str = "attachment",
    _: User = Depends(get_current_active_user),
    use_case: DownloadOrderFile = Depends(get_download_order_file_use_case),
) -> Response:
    """Stream the file's raw bytes. Gated identically to the list route
    above (login only): downloading is not write-gated, since it does not
    alter the order."""
    file, data, content_type = await use_case.execute(order_id=order_id, file_id=file_id)
    return file_download_response(
        data, file.file_name, content_type=content_type, disposition=disposition
    )


@router.post(
    "/{order_id}/files",
    response_model=OrderFileResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_max_upload_size)],
)
async def upload_order_file(
    order_id: int,
    file: UploadFile,
    category: OrderFileCategory = Form(...),
    actor: User = Depends(get_current_active_user),
    use_case: UploadOrderFile = Depends(get_upload_order_file_use_case),
) -> OrderFileResult:
    data, file_name, content_type = await read_upload(file)
    return await use_case.execute(
        actor=actor,
        order_id=order_id,
        data=data,
        file_name=file_name,
        content_type=content_type,
        category=category,
    )


@router.post(
    "/{order_id}/items/{order_item_id}/deliveries/{delivery_id}/pictures",
    response_model=OrderFileResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_max_upload_size)],
)
async def upload_delivery_picture(
    order_id: int,
    order_item_id: int,
    delivery_id: int,
    file: UploadFile,
    actor: User = Depends(get_current_active_user),
    use_case: UploadDeliveryPicture = Depends(get_upload_delivery_picture_use_case),
) -> OrderFileResult:
    """Stores a JPEG, PNG or WebP picture of one delivery row of an order
    item, such as a photo of damaged goods, as an order file of the picture
    category that names the row. Requires receive:deliveries. A row that is
    not on the item, or an item not on the order, answers 404."""
    data, file_name, content_type = await read_upload(file)
    return await use_case.execute(
        actor=actor,
        order_id=order_id,
        order_item_id=order_item_id,
        delivery_id=delivery_id,
        data=data,
        file_name=file_name,
        content_type=content_type,
    )


@router.delete("/{order_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order_file(
    order_id: int,
    file_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteOrderFile = Depends(get_delete_order_file_use_case),
) -> None:
    await use_case.execute(actor=actor, file_id=file_id)
