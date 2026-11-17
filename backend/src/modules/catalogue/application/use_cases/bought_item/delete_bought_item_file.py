"""
Deletes a bought item file by delegating to the generic item-file deletion
handler.
"""

from src.modules.catalogue.application.use_cases.bought_item._file_kind import BOUGHT_ITEM_FILE_KIND
from src.modules.catalogue.domain.entities.bought_item_file import BoughtItemFile
from src.modules.platform.application.services.file_attachments.base import DeleteItemFileBase


class DeleteBoughtItemFile(DeleteItemFileBase[BoughtItemFile]):
    _kind = BOUGHT_ITEM_FILE_KIND
