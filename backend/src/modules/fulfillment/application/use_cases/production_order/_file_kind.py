"""
The production order file family's declared shape for the generic
item-files use-case core. See src/modules/platform/application/services/file_attachments/config.py
for what each field means.

These are inspection evidence files, a scanned or exported CMM report or a
photo of a gauge reading, so every category takes a PDF or an image. Unlike
catalogue images, evidence is kept byte for byte as uploaded, so
`image_categories` is empty. Only the upload runs on the shared core: the
list, rename, delete and download use cases each word their own
write:inspections refusal, so `write_rule` carries the upload's wording.
"""

from src.modules.fulfillment.application.dto.production_order_file_dto import (
    ProductionOrderFileResult,
)
from src.modules.fulfillment.domain.entities.production_order_file import ProductionOrderFile
from src.modules.fulfillment.domain.errors import ProductionOrderFileInvalidTypeError
from src.modules.fulfillment.domain.errors import ProductionOrderFileNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderFileTooLargeError
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.domain.value_objects.production_order_file_category import (
    ProductionOrderFileCategory,
)
from src.modules.platform.application.services.file_attachments.config import ItemFileKind
from src.modules.platform.application.services.file_attachments.config import MiB
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission


def _assert_can_upload_evidence(actor: User) -> None:
    if not actor.has_permission(Permission.WRITE_INSPECTIONS):
        raise InsufficientPermissionsError(
            f"User #{actor.id} ({actor.full_name}) cannot upload inspection evidence files."
        )


PRODUCTION_ORDER_FILE_KIND = ItemFileKind(
    item_label="production order",
    storage_prefix="production_orders",
    fk_field="production_order_id",
    entity_cls=ProductionOrderFile,
    result_cls=ProductionOrderFileResult,
    image_categories=frozenset(),
    max_bytes={ProductionOrderFileCategory.MEASUREMENT_REPORT: 50 * MiB},
    extra_validators={},
    pdf_fallback_message=(
        "{category} category requires application/pdf or an image (JPEG/PNG/WebP), "
        "got {content_type!r}."
    ),
    item_not_found_error=ProductionOrderNotFoundError,
    file_not_found_error=ProductionOrderFileNotFoundError,
    file_too_large_error=ProductionOrderFileTooLargeError,
    file_invalid_type_error=ProductionOrderFileInvalidTypeError,
    write_rule=_assert_can_upload_evidence,
)
