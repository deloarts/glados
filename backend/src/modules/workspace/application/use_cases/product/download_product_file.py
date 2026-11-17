"""
Byte-serving counterpart to GetProductFiles. Gated the same way as the
list route (login only, enforced at the endpoint): the download gate
must equal the family's list gate, never the write gate, since the list
route already discloses this file's metadata (and, today, a fetchable
URL) to anyone who can call it.
"""

from src.modules.platform.application.services.file_attachments.base import DownloadItemFileBase
from src.modules.workspace.application.use_cases.product._file_kind import PRODUCT_FILE_KIND
from src.modules.workspace.domain.entities.product_file import ProductFile


class DownloadProductFile(DownloadItemFileBase[ProductFile]):
    _kind = PRODUCT_FILE_KIND

    async def execute(self, product_id: int, file_id: int) -> tuple[ProductFile, bytes, str]:
        return await super().execute(product_id, file_id)
