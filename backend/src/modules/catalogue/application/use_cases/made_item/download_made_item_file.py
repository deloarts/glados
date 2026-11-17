"""
Byte-serving counterpart to GetMadeItemFiles. Gated the same way as the
list route above (login only, enforced at the endpoint): the download gate
must equal the family's list gate, never the write gate, since the list
route already discloses this file's metadata (and, today, a fetchable URL)
to anyone who can call it.
"""

from src.modules.catalogue.application.use_cases.made_item._file_kind import MADE_ITEM_FILE_KIND
from src.modules.catalogue.domain.entities.made_item_file import MadeItemFile
from src.modules.platform.application.services.file_attachments.base import DownloadItemFileBase


class DownloadMadeItemFile(DownloadItemFileBase[MadeItemFile]):
    _kind = MADE_ITEM_FILE_KIND
