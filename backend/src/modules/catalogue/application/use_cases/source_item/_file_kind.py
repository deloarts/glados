"""
The source-item file family's declared shape for the generic _item_files
use-case core (fields in src/modules/platform/application/services/file_attachments/config.py).
Every source-item file use case reads its rules from here. A source item is
raw stock, so it has no STEP geometry, but it can carry a mesh of the stock
shape and therefore keeps the MESH validator.
"""

from src.modules.catalogue.application.dto.source_item_file_dto import SourceItemFileResult
from src.modules.catalogue.domain.entities.source_item_file import SourceItemFile
from src.modules.catalogue.domain.errors import SourceItemFileInvalidTypeError
from src.modules.catalogue.domain.errors import SourceItemFileNotFoundError
from src.modules.catalogue.domain.errors import SourceItemFileTooLargeError
from src.modules.catalogue.domain.errors import SourceItemNotFoundError
from src.modules.catalogue.domain.policies.source_item_rules import SourceItemCatalogueRules
from src.modules.catalogue.domain.value_objects.source_item_file_category import (
    SourceItemFileCategory,
)
from src.modules.platform.application.services.file_attachments.config import MESH_VALIDATOR
from src.modules.platform.application.services.file_attachments.config import ItemFileKind
from src.modules.platform.application.services.file_attachments.config import MiB

SOURCE_ITEM_FILE_KIND = ItemFileKind(
    item_label="source item",
    storage_prefix="source_items/catalogue",
    fk_field="source_item_id",
    entity_cls=SourceItemFile,
    result_cls=SourceItemFileResult,
    # Pictures are not files; see application.services.item_picture_store.
    image_categories=frozenset(),
    max_bytes={
        SourceItemFileCategory.MESH: 100 * MiB,
        SourceItemFileCategory.PDF: 50 * MiB,
    },
    extra_validators={
        SourceItemFileCategory.MESH: MESH_VALIDATOR,
    },
    pdf_fallback_message=(
        "PDF category requires application/pdf content type (got {content_type!r})."
    ),
    item_not_found_error=SourceItemNotFoundError,
    file_not_found_error=SourceItemFileNotFoundError,
    file_too_large_error=SourceItemFileTooLargeError,
    file_invalid_type_error=SourceItemFileInvalidTypeError,
    write_rule=SourceItemCatalogueRules.assert_can_update,
)
