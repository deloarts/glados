"""HTTP schemas for order file upload, storage, and retrieval."""

from datetime import datetime

from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse


class OrderFileResponse(EntityResponse):
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
    url: str | None
    # The delivery row a picture taken at goods receipt documents, None for
    # a file uploaded to the order itself.
    delivery_id: int | None = None
