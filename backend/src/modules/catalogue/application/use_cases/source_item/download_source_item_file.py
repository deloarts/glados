"""
Byte-serving counterpart to GetSourceItemFiles. Gated the same way as the
list route (login only): the download gate must equal the family's
list gate, never the write gate, since the list route already discloses
this file's metadata to anyone who can call it.
"""

from src.modules.catalogue.application.use_cases.source_item._file_kind import SOURCE_ITEM_FILE_KIND
from src.modules.catalogue.domain.entities.source_item_file import SourceItemFile
from src.modules.platform.application.services.file_attachments.base import DownloadItemFileBase


class DownloadSourceItemFile(DownloadItemFileBase[SourceItemFile]):
    _kind = SOURCE_ITEM_FILE_KIND
