"""HTTP schemas for the documents of a supplier's offer on a quote request."""

from datetime import datetime

from src.modules.fulfillment.domain.value_objects.quote_file_category import QuoteFileCategory
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse


class QuoteRequestFileResponse(EntityResponse):
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
    url: str | None
