"""
Uploads a file (image, STEP, mesh, PDF) to a bought catalogue item with
validation and storage.
"""

from src.modules.catalogue.application.dto.bought_item_file_dto import BoughtItemFileResult
from src.modules.catalogue.application.use_cases.bought_item._file_kind import BOUGHT_ITEM_FILE_KIND
from src.modules.catalogue.domain.entities.bought_item_file import BoughtItemFile
from src.modules.platform.application.services.file_attachments.base import UploadItemFileBase


class UploadBoughtItemFile(UploadItemFileBase[BoughtItemFile, BoughtItemFileResult]):
    _kind = BOUGHT_ITEM_FILE_KIND
