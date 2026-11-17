"""
Byte-serving counterpart to GetOrderFiles. Gated the same way as the list
route (login only, enforced at the endpoint): the download gate must
equal the family's list gate, never the write gate, since the list route
already discloses this file's metadata (and, today, a fetchable URL) to
anyone who can call it.
"""

from src.modules.fulfillment.application.use_cases.order._file_kind import ORDER_FILE_KIND
from src.modules.fulfillment.domain.entities.order_file import OrderFile
from src.modules.platform.application.services.file_attachments.base import DownloadItemFileBase


class DownloadOrderFile(DownloadItemFileBase[OrderFile]):
    _kind = ORDER_FILE_KIND

    async def execute(self, order_id: int, file_id: int) -> tuple[OrderFile, bytes, str]:
        return await super().execute(order_id, file_id)
