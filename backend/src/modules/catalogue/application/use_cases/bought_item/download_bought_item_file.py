"""
Byte-serving counterpart to GetBoughtItemFiles. Authorization gate equals
the list route (login only), never the write gate, since the list route
already discloses this file's metadata to anyone who can call it.
"""

from src.modules.catalogue.application.use_cases.bought_item._file_kind import BOUGHT_ITEM_FILE_KIND
from src.modules.catalogue.domain.entities.bought_item_file import BoughtItemFile
from src.modules.platform.application.services.file_attachments.base import DownloadItemFileBase


class DownloadBoughtItemFile(DownloadItemFileBase[BoughtItemFile]):
    _kind = BOUGHT_ITEM_FILE_KIND
