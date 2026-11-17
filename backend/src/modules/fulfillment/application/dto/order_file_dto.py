"""
DTOs for order file attachments: the upload history and metadata recorded
for files attached to an order (delivery notes, invoices, and similar
documents).
"""

from datetime import datetime

from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory
from src.modules.platform.application.dto.base import ResultBase


class OrderFileResult(ResultBase):
    order_id: int
    file_name: str
    stored_name: str
    mime_type: str
    size_bytes: int
    storage_path: str
    sha256: str
    category: OrderFileCategory
    created: datetime
    uploaded_by_user_id: int
    url: str | None  # None when storage is disabled or url generation failed
    # The delivery row a picture taken at goods receipt documents.
    delivery_id: int | None = None
