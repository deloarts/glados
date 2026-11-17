"""
Retrieves all files associated with a source item.
"""

from src.modules.catalogue.application.dto.source_item_file_dto import SourceItemFileResult
from src.modules.catalogue.application.use_cases.source_item._file_kind import SOURCE_ITEM_FILE_KIND
from src.modules.catalogue.domain.entities.source_item_file import SourceItemFile
from src.modules.platform.application.services.file_attachments.base import GetItemFilesBase


class GetSourceItemFiles(GetItemFilesBase[SourceItemFile, SourceItemFileResult]):
    _kind = SOURCE_ITEM_FILE_KIND
