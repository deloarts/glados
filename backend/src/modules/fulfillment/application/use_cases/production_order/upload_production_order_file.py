"""
Uploads an inspection evidence file (a PDF or an image) to a production
order on the shared item-file upload core. Evidence is stored byte for byte
as uploaded, see production_order/_file_kind.py.
"""

from src.modules.fulfillment.application.dto.production_order_file_dto import (
    ProductionOrderFileResult,
)
from src.modules.fulfillment.application.use_cases.production_order._file_kind import (
    PRODUCTION_ORDER_FILE_KIND,
)
from src.modules.fulfillment.domain.entities.production_order_file import ProductionOrderFile
from src.modules.fulfillment.domain.errors import ProductionOrderFileInvalidTypeError
from src.modules.fulfillment.domain.errors import ProductionOrderFileTooLargeError
from src.modules.fulfillment.domain.value_objects.production_order_file_category import (
    ProductionOrderFileCategory,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_file_repository import (
    IProductionOrderFileRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.application.services.file_attachments.base import UploadItemFileBase
from src.modules.platform.application.services.file_attachments.config import IMAGE_CONTENT_TYPES
from src.modules.platform.application.services.file_attachments.config import MiB
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def _validate(category: ProductionOrderFileCategory, content_type: str, size: int) -> str:
    limit = PRODUCTION_ORDER_FILE_KIND.max_bytes[category]
    if size > limit:
        mb = limit // MiB
        raise ProductionOrderFileTooLargeError(
            f"{category.value} files must be ≤ {mb} MB (got {size} bytes)."
        )
    if content_type == "application/pdf":
        return ".pdf"
    if content_type in IMAGE_CONTENT_TYPES:
        return IMAGE_CONTENT_TYPES[content_type]
    raise ProductionOrderFileInvalidTypeError(
        PRODUCTION_ORDER_FILE_KIND.pdf_fallback_message.format(
            category=category.value, content_type=content_type
        )
    )


class UploadProductionOrderFile(UploadItemFileBase[ProductionOrderFile, ProductionOrderFileResult]):
    _kind = PRODUCTION_ORDER_FILE_KIND

    def __init__(
        self,
        order_repo: IProductionOrderRepository,
        file_repo: IProductionOrderFileRepository,
        storage: IStoragePort | None,
        *,
        uow: IUnitOfWork,
    ) -> None:
        super().__init__(order_repo, file_repo, storage, uow=uow)

    def _validate_upload(
        self, category: ProductionOrderFileCategory, content_type: str, file_name: str, size: int
    ) -> str:
        return _validate(category, content_type, size)

    async def execute(
        self,
        actor: User,
        order_id: int,
        data: bytes,
        file_name: str,
        content_type: str,
        category: ProductionOrderFileCategory,
    ) -> ProductionOrderFileResult:
        return await super().execute(actor, order_id, data, file_name, content_type, category)
