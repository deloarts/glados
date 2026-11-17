"""
A document a supplier sent with its offer on a quote request, such as the
offer PDF. Stored content lives in the storage adapter; this entity tracks
the metadata and the sha256 used to detect duplicate uploads.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.fulfillment.domain.value_objects.quote_file_category import QuoteFileCategory
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class QuoteRequestFile(Entity):
    supplier_row_id: int  # the supplier entry of the quote request

    file_name: str
    stored_name: str
    mime_type: str
    size_bytes: int

    storage_path: str
    sha256: str

    category: QuoteFileCategory

    created: datetime
    uploaded_by_user_id: int
