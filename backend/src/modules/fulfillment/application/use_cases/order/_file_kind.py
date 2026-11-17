"""
The order file family's declared shape for the generic item-files use-case
core. See src/modules/platform/application/services/file_attachments/config.py for what each
field means.

Every order category accumulates, PICTURE takes images and every other
category takes PDFs. Pictures are documentation and are stored as uploaded,
never reprocessed, so `image_categories` is empty. The upload validates with
its own long-standing messages (see upload_order_file._validate); the limits
declared here are the same ones.
"""

from src.modules.fulfillment.application.dto.order_file_dto import OrderFileResult
from src.modules.fulfillment.domain.entities.order_file import OrderFile
from src.modules.fulfillment.domain.errors import OrderFileInvalidTypeError
from src.modules.fulfillment.domain.errors import OrderFileNotFoundError
from src.modules.fulfillment.domain.errors import OrderFileTooLargeError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory
from src.modules.platform.application.services.file_attachments.config import ItemFileKind
from src.modules.platform.application.services.file_attachments.config import MiB
from src.modules.platform.ports.outbound.storage_port import IStoragePort

ORDER_FILE_MAX_BYTES = 25 * MiB  # per order document, whatever its category


class _OrderFileKind(ItemFileKind[OrderFile, OrderFileResult, OrderFileCategory]):
    """The order family's shape, whose results also name the delivery row a
    picture documents, a field the other families do not have."""

    def to_result(
        self,
        entity: OrderFile,
        storage: IStoragePort | None,
        url: str | None = None,
        *,
        from_pdm: bool = False,
    ) -> OrderFileResult:
        result = super().to_result(entity, storage, url, from_pdm=from_pdm)
        return result.model_copy(update={"delivery_id": entity.delivery_id})


ORDER_FILE_KIND = _OrderFileKind(
    item_label="order",
    storage_prefix="bought_items/orders",
    fk_field="order_id",
    entity_cls=OrderFile,
    result_cls=OrderFileResult,
    image_categories=frozenset(),
    max_bytes=dict.fromkeys(OrderFileCategory, ORDER_FILE_MAX_BYTES),
    extra_validators={},
    pdf_fallback_message="Order documents must be PDFs (got {content_type!r}).",
    item_not_found_error=OrderNotFoundError,
    file_not_found_error=OrderFileNotFoundError,
    file_too_large_error=OrderFileTooLargeError,
    file_invalid_type_error=OrderFileInvalidTypeError,
    write_rule=OrderRules.assert_can_manage_files,
)
