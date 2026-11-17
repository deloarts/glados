"""
Fetch the list of files attached to a made item in the catalogue.
"""

from src.modules.catalogue.application.dto.made_item_file_dto import MadeItemFileResult
from src.modules.catalogue.application.use_cases.made_item._file_kind import MADE_ITEM_FILE_KIND
from src.modules.catalogue.domain.entities.made_item_file import MadeItemFile
from src.modules.platform.application.services.file_attachments.base import GetItemFilesBase


class GetMadeItemFiles(GetItemFilesBase[MadeItemFile, MadeItemFileResult]):
    _kind = MADE_ITEM_FILE_KIND
