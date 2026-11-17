"""
Deletes a file attached to a source item, using the shared generic item-file use case core
configured with the source item file family's rules.
"""

from src.modules.catalogue.application.use_cases.source_item._file_kind import SOURCE_ITEM_FILE_KIND
from src.modules.catalogue.domain.entities.source_item_file import SourceItemFile
from src.modules.platform.application.services.file_attachments.base import DeleteItemFileBase


class DeleteSourceItemFile(DeleteItemFileBase[SourceItemFile]):
    _kind = SOURCE_ITEM_FILE_KIND
