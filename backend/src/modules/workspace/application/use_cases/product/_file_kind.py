"""
The product file family's declared shape for the generic item-files
use-case core. See src/modules/platform/application/services/file_attachments/config.py for what
each field means.

A product carries reference images and specification PDFs only; concrete
geometry lives on the made items beneath it. Its write rule needs the
product itself (manage:projects or being its designated user), so there is
no actor-only `write_rule`: the upload, update and delete use cases resolve
the product first and apply ProductRules themselves.
"""

from src.modules.platform.application.services.file_attachments.config import ItemFileKind
from src.modules.platform.application.services.file_attachments.config import MiB
from src.modules.workspace.application.dto.product_file_dto import ProductFileResult
from src.modules.workspace.domain.entities.product_file import ProductFile
from src.modules.workspace.domain.errors import ProductFileInvalidTypeError
from src.modules.workspace.domain.errors import ProductFileNotFoundError
from src.modules.workspace.domain.errors import ProductFileTooLargeError
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory

PRODUCT_FILE_KIND = ItemFileKind(
    item_label="product",
    # No "catalogue/" sub-area: that segment separates catalogue attachments
    # from order ones on bought and made items. Products have no such split.
    storage_prefix="products",
    fk_field="product_id",
    entity_cls=ProductFile,
    result_cls=ProductFileResult,
    image_categories=ProductFileCategory.images(),
    max_bytes={
        ProductFileCategory.THUMBNAIL: 2 * MiB,
        ProductFileCategory.IMAGE: 10 * MiB,
        ProductFileCategory.PDF: 50 * MiB,
        ProductFileCategory.DEVICE_RENDERING: 10 * MiB,
        ProductFileCategory.DEVICE_ASSEMBLY: 10 * MiB,
        ProductFileCategory.DEVICE_OVERVIEW: 10 * MiB,
    },
    extra_validators={},
    pdf_fallback_message=(
        "PDF category requires application/pdf content type (got {content_type!r})."
    ),
    item_not_found_error=ProductNotFoundError,
    file_not_found_error=ProductFileNotFoundError,
    file_too_large_error=ProductFileTooLargeError,
    file_invalid_type_error=ProductFileInvalidTypeError,
    write_rule=None,
    # The top-down overview is often a vector export; renderings stay raster.
    svg_categories=frozenset({ProductFileCategory.DEVICE_OVERVIEW}),
)
