"""
The offer document family's declared shape for the generic item-files core:
documents of a supplier entry of a quote request, PDFs in every category,
written under write:orders like the rest of a quote request.
"""

from src.modules.fulfillment.application.dto.quote_request_file_dto import QuoteRequestFileResult
from src.modules.fulfillment.domain.entities.quote_request_file import QuoteRequestFile
from src.modules.fulfillment.domain.errors import QuoteRequestFileInvalidTypeError
from src.modules.fulfillment.domain.errors import QuoteRequestFileNotFoundError
from src.modules.fulfillment.domain.errors import QuoteRequestFileTooLargeError
from src.modules.fulfillment.domain.errors import QuoteRequestSupplierNotFoundError
from src.modules.fulfillment.domain.services.quote_request_rules import (
    assert_can_write_quote_requests,
)
from src.modules.fulfillment.domain.value_objects.quote_file_category import QuoteFileCategory
from src.modules.platform.application.services.file_attachments.config import ItemFileKind
from src.modules.platform.application.services.file_attachments.config import MiB

QUOTE_FILE_MAX_BYTES = 25 * MiB

QUOTE_FILE_KIND = ItemFileKind(
    item_label="offer",
    storage_prefix="procurement/quote_requests",
    fk_field="supplier_row_id",
    entity_cls=QuoteRequestFile,
    result_cls=QuoteRequestFileResult,
    image_categories=frozenset(),
    max_bytes=dict.fromkeys(QuoteFileCategory, QUOTE_FILE_MAX_BYTES),
    extra_validators={},
    pdf_fallback_message="Offer documents must be PDFs (got {content_type!r}).",
    item_not_found_error=QuoteRequestSupplierNotFoundError,
    file_not_found_error=QuoteRequestFileNotFoundError,
    file_too_large_error=QuoteRequestFileTooLargeError,
    file_invalid_type_error=QuoteRequestFileInvalidTypeError,
    write_rule=assert_can_write_quote_requests,
)
