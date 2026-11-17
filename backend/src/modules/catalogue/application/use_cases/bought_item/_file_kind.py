"""
The bought-item file family's declared shape for the generic item-files
use-case core (fields in src/modules/platform/application/services/file_attachments/config.py).
Every bought-item file use case reads its rules from here.
"""

from src.modules.catalogue.application.dto.bought_item_file_dto import BoughtItemFileResult
from src.modules.catalogue.domain.entities.bought_item_file import BoughtItemFile
from src.modules.catalogue.domain.errors import BoughtItemFileInvalidTypeError
from src.modules.catalogue.domain.errors import BoughtItemFileNotFoundError
from src.modules.catalogue.domain.errors import BoughtItemFileTooLargeError
from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.policies.bought_item_rules import BoughtItemCatalogueRules
from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)
from src.modules.platform.application.services.file_attachments.config import DXF_VALIDATOR
from src.modules.platform.application.services.file_attachments.config import MESH_VALIDATOR
from src.modules.platform.application.services.file_attachments.config import STEP_VALIDATOR
from src.modules.platform.application.services.file_attachments.config import ItemFileKind
from src.modules.platform.application.services.file_attachments.config import MiB

BOUGHT_ITEM_FILE_KIND = ItemFileKind(
    item_label="bought item",
    storage_prefix="bought_items/catalogue",
    fk_field="bought_item_id",
    entity_cls=BoughtItemFile,
    result_cls=BoughtItemFileResult,
    # Pictures are not files; see application.services.item_picture_store.
    image_categories=frozenset(),
    max_bytes={
        BoughtItemFileCategory.STEP: 100 * MiB,
        BoughtItemFileCategory.MESH: 100 * MiB,
        BoughtItemFileCategory.DRAWING: 50 * MiB,
        BoughtItemFileCategory.DXF: 50 * MiB,
        BoughtItemFileCategory.PDF: 50 * MiB,
    },
    extra_validators={
        BoughtItemFileCategory.STEP: STEP_VALIDATOR,
        BoughtItemFileCategory.MESH: MESH_VALIDATOR,
        BoughtItemFileCategory.DXF: DXF_VALIDATOR,
    },
    # Fixed "PDF category" wording even for DRAWING, unlike the made-item
    # template; test_item_file_behaviour.py::TestPdfFallbackMessageWording pins it.
    pdf_fallback_message=(
        "PDF category requires application/pdf content type (got {content_type!r})."
    ),
    item_not_found_error=BoughtItemNotFoundError,
    file_not_found_error=BoughtItemFileNotFoundError,
    file_too_large_error=BoughtItemFileTooLargeError,
    file_invalid_type_error=BoughtItemFileInvalidTypeError,
    write_rule=BoughtItemCatalogueRules.assert_can_update,
)
