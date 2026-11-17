"""
The documents of a supplier's offer on a quote request, on the shared
item-file core: list, upload, download and delete. Every category takes PDFs
only. Listing and downloading need a login, writing needs write:orders.
"""

from src.modules.fulfillment.application.dto.quote_request_file_dto import QuoteRequestFileResult
from src.modules.fulfillment.application.use_cases.quote_request._file_kind import QUOTE_FILE_KIND
from src.modules.fulfillment.domain.entities.quote_request_file import QuoteRequestFile
from src.modules.fulfillment.domain.value_objects.quote_file_category import QuoteFileCategory
from src.modules.platform.application.services.file_attachments.base import DeleteItemFileBase
from src.modules.platform.application.services.file_attachments.base import DownloadItemFileBase
from src.modules.platform.application.services.file_attachments.base import GetItemFilesBase
from src.modules.platform.application.services.file_attachments.base import UploadItemFileBase
from src.modules.platform.domain.entities.user import User


class GetOfferFiles(GetItemFilesBase[QuoteRequestFile, QuoteRequestFileResult]):
    _kind = QUOTE_FILE_KIND

    async def execute(self, item_id: int) -> list[QuoteRequestFileResult]:
        return await super().execute(item_id)


class UploadOfferFile(UploadItemFileBase[QuoteRequestFile, QuoteRequestFileResult]):
    _kind = QUOTE_FILE_KIND

    async def execute(
        self,
        actor: User,
        item_id: int,
        data: bytes,
        file_name: str,
        content_type: str,
        category: QuoteFileCategory,
    ) -> QuoteRequestFileResult:
        return await super().execute(actor, item_id, data, file_name, content_type, category)


class DownloadOfferFile(DownloadItemFileBase[QuoteRequestFile]):
    _kind = QUOTE_FILE_KIND

    async def execute(self, item_id: int, file_id: int) -> tuple[QuoteRequestFile, bytes, str]:
        return await super().execute(item_id, file_id)


class DeleteOfferFile(DeleteItemFileBase[QuoteRequestFile]):
    _kind = QUOTE_FILE_KIND
