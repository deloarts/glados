"""
DTOs for the documents a supplier sent with its offer on a quote request.
"""

from datetime import datetime

from src.modules.fulfillment.domain.value_objects.quote_file_category import QuoteFileCategory
from src.modules.platform.application.dto.base import ResultBase


class QuoteRequestFileResult(ResultBase):
    supplier_row_id: int
    file_name: str
    stored_name: str
    mime_type: str
    size_bytes: int
    storage_path: str
    sha256: str
    category: QuoteFileCategory
    created: datetime
    uploaded_by_user_id: int
    url: str | None  # None when storage is disabled or url generation failed
