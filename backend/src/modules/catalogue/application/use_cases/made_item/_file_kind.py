"""
The made-item file family's declared shape for the generic `_item_files`
use-case core (fields in src/modules/platform/application/services/file_attachments/config.py).
Every made-item file use case reads its rules from here. Its PDF fallback
message names the category, because DRAWING falls back to the same PDF check
as PDF.
"""

from src.modules.catalogue.application.dto.made_item_file_dto import MadeItemFileResult
from src.modules.catalogue.domain.entities.made_item_file import MadeItemFile
from src.modules.catalogue.domain.errors import MadeItemFileInvalidTypeError
from src.modules.catalogue.domain.errors import MadeItemFileNotFoundError
from src.modules.catalogue.domain.errors import MadeItemFileTooLargeError
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.modules.platform.application.services.file_attachments.config import DXF_VALIDATOR
from src.modules.platform.application.services.file_attachments.config import MESH_VALIDATOR
from src.modules.platform.application.services.file_attachments.config import STEP_VALIDATOR
from src.modules.platform.application.services.file_attachments.config import ItemFileKind
from src.modules.platform.application.services.file_attachments.config import MiB

MADE_ITEM_FILE_KIND = ItemFileKind(
    item_label="made item",
    storage_prefix="made_items/catalogue",
    fk_field="made_item_id",
    entity_cls=MadeItemFile,
    result_cls=MadeItemFileResult,
    # Pictures are not files; see application.services.item_picture_store.
    image_categories=frozenset(),
    max_bytes={
        MadeItemFileCategory.STEP: 100 * MiB,
        MadeItemFileCategory.MESH: 100 * MiB,
        MadeItemFileCategory.DRAWING: 50 * MiB,
        MadeItemFileCategory.DXF: 50 * MiB,
        MadeItemFileCategory.PDF: 50 * MiB,
    },
    extra_validators={
        MadeItemFileCategory.STEP: STEP_VALIDATOR,
        MadeItemFileCategory.MESH: MESH_VALIDATOR,
        MadeItemFileCategory.DXF: DXF_VALIDATOR,
    },
    pdf_fallback_message=(
        "{category} category requires application/pdf content type (got {content_type!r})."
    ),
    item_not_found_error=MadeItemNotFoundError,
    file_not_found_error=MadeItemFileNotFoundError,
    file_too_large_error=MadeItemFileTooLargeError,
    file_invalid_type_error=MadeItemFileInvalidTypeError,
    write_rule=MadeItemCatalogueRules.assert_can_update,
)
