"""
Document endpoints of a supplier entry of a quote request, such as the
supplier's offer PDF.

Routes (all under /quote-request-suppliers/{row_id}/files):
  GET    /                  - list files (url=None when storage disabled)
  POST   /                  - upload a PDF (multipart; requires storage)
  GET    /{file_id}         - download file bytes (same gate as list)
  DELETE /{file_id}         - delete file and storage object
"""

from fastapi import Depends
from fastapi import Form
from fastapi import Response
from fastapi import UploadFile
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_delete_offer_file_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_download_offer_file_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_offer_files_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_upload_offer_file_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.quote_request_file_schema import (
    QuoteRequestFileResponse,
)
from src.modules.fulfillment.application.dto.quote_request_file_dto import QuoteRequestFileResult
from src.modules.fulfillment.application.use_cases.quote_request.offer_files import DeleteOfferFile
from src.modules.fulfillment.application.use_cases.quote_request.offer_files import (
    DownloadOfferFile,
)
from src.modules.fulfillment.application.use_cases.quote_request.offer_files import GetOfferFiles
from src.modules.fulfillment.application.use_cases.quote_request.offer_files import UploadOfferFile
from src.modules.fulfillment.domain.value_objects.quote_file_category import QuoteFileCategory
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.download_headers import file_download_response
from src.modules.platform.adapters.inbound.api.download_headers import read_upload
from src.modules.platform.adapters.inbound.api.upload_limits import enforce_max_upload_size
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/{row_id}/files", response_model=list[QuoteRequestFileResponse])
async def list_offer_files(
    row_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetOfferFiles = Depends(get_offer_files_use_case),
) -> list[QuoteRequestFileResult]:
    return await use_case.execute(row_id)


@router.get("/{row_id}/files/{file_id}")
async def download_offer_file(
    row_id: int,
    file_id: int,
    disposition: str = "attachment",
    _: User = Depends(get_current_active_user),
    use_case: DownloadOfferFile = Depends(get_download_offer_file_use_case),
) -> Response:
    """Streams the file's bytes; gated like the list route (login only)."""
    file, data, content_type = await use_case.execute(row_id, file_id)
    return file_download_response(
        data, file.file_name, content_type=content_type, disposition=disposition
    )


@router.post(
    "/{row_id}/files",
    response_model=QuoteRequestFileResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_max_upload_size)],
)
async def upload_offer_file(
    row_id: int,
    file: UploadFile,
    category: QuoteFileCategory = Form(...),
    actor: User = Depends(get_current_active_user),
    use_case: UploadOfferFile = Depends(get_upload_offer_file_use_case),
) -> QuoteRequestFileResult:
    data, file_name, content_type = await read_upload(file)
    return await use_case.execute(actor, row_id, data, file_name, content_type, category)


@router.delete("/{row_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_offer_file(
    row_id: int,
    file_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteOfferFile = Depends(get_delete_offer_file_use_case),
) -> None:
    await use_case.execute(actor, file_id)
