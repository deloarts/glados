"""
The meeting file family's declared shape for the generic item-files
use-case core. See
src/modules/platform/application/services/file_attachments/config.py for
what each field means.

A meeting holds images, such as those pasted into a card, and PDF
documents, any number of each, under a storage prefix of its own, which the
nightly sweep of unreferenced blobs walks. Writing them needs
write:meetings.
"""

from src.modules.platform.application.services.file_attachments.config import ItemFileKind
from src.modules.platform.application.services.file_attachments.config import MiB
from src.modules.workspace.application.dto.meeting_dto import MeetingFileResult
from src.modules.workspace.domain.entities.meeting import MeetingFile
from src.modules.workspace.domain.errors import MeetingFileInvalidTypeError
from src.modules.workspace.domain.errors import MeetingFileNotFoundError
from src.modules.workspace.domain.errors import MeetingFileTooLargeError
from src.modules.workspace.domain.errors import MeetingNotFoundError
from src.modules.workspace.domain.services.meeting_rules import MeetingRules
from src.modules.workspace.domain.value_objects.meeting import MeetingFileCategory

MEETING_FILE_STORAGE_PREFIX = "meetings"

MEETING_FILE_KIND = ItemFileKind(
    item_label="meeting",
    storage_prefix=MEETING_FILE_STORAGE_PREFIX,
    fk_field="meeting_id",
    entity_cls=MeetingFile,
    result_cls=MeetingFileResult,
    image_categories=MeetingFileCategory.images(),
    max_bytes={MeetingFileCategory.IMAGE: 10 * MiB, MeetingFileCategory.PDF: 50 * MiB},
    extra_validators={},
    pdf_fallback_message=(
        "PDF category requires application/pdf content type (got {content_type!r})."
    ),
    item_not_found_error=MeetingNotFoundError,
    file_not_found_error=MeetingFileNotFoundError,
    file_too_large_error=MeetingFileTooLargeError,
    file_invalid_type_error=MeetingFileInvalidTypeError,
    write_rule=MeetingRules.assert_can_write,
)
