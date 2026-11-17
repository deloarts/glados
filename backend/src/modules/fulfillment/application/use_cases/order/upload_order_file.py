"""
Uploads a document or picture to a purchase order on the shared item-file
upload core. The PICTURE category accepts JPEG/PNG/WebP images; every other
category accepts only PDFs.
"""

from src.modules.fulfillment.application.dto.order_file_dto import OrderFileResult
from src.modules.fulfillment.application.use_cases.order._file_kind import ORDER_FILE_KIND
from src.modules.fulfillment.application.use_cases.order._file_kind import ORDER_FILE_MAX_BYTES
from src.modules.fulfillment.domain.entities.order_file import OrderFile
from src.modules.fulfillment.domain.errors import OrderFileInvalidTypeError
from src.modules.fulfillment.domain.errors import OrderFileTooLargeError
from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory
from src.modules.fulfillment.ports.outbound.repositories.order_file_repository import (
    IOrderFileRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.platform.application.services.file_attachments.base import UploadItemFileBase
from src.modules.platform.application.services.file_attachments.config import IMAGE_CONTENT_TYPES
from src.modules.platform.application.services.file_attachments.config import MiB
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def _validate(category: OrderFileCategory, content_type: str) -> str:
    if category == OrderFileCategory.PICTURE:
        if content_type not in IMAGE_CONTENT_TYPES:
            raise OrderFileInvalidTypeError(
                f"Pictures must be an image (JPEG/PNG/WebP), got {content_type!r}."
            )
        return IMAGE_CONTENT_TYPES[content_type]

    if content_type != "application/pdf":
        raise OrderFileInvalidTypeError(
            ORDER_FILE_KIND.pdf_fallback_message.format(content_type=content_type)
        )
    return ".pdf"


class UploadOrderFile(UploadItemFileBase[OrderFile, OrderFileResult]):
    _kind = ORDER_FILE_KIND

    def __init__(
        self,
        order_repo: IOrderRepository,
        file_repo: IOrderFileRepository,
        storage: IStoragePort | None,
        *,
        uow: IUnitOfWork,
    ) -> None:
        super().__init__(order_repo, file_repo, storage, uow=uow)

    def _validate_upload(
        self, category: OrderFileCategory, content_type: str, file_name: str, size: int
    ) -> str:
        if size > ORDER_FILE_MAX_BYTES:
            mb = ORDER_FILE_MAX_BYTES // MiB
            raise OrderFileTooLargeError(f"Order documents must be ≤ {mb} MB (got {size} bytes).")
        return _validate(category, content_type)

    async def execute(
        self,
        actor: User,
        order_id: int,
        data: bytes,
        file_name: str,
        content_type: str,
        category: OrderFileCategory,
    ) -> OrderFileResult:
        return await super().execute(actor, order_id, data, file_name, content_type, category)
