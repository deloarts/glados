"""
An uploaded file attached to an order, such as a purchase confirmation or
delivery note. Stored content lives in the storage adapter; this entity
tracks the metadata and the sha256 used to detect duplicate uploads. A
picture taken at goods receipt, such as a photo of damaged goods, also names
the delivery row it documents.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class OrderFile(Entity):
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

    # The delivery row (OrderItemDelivery) a picture documents, None for
    # every file uploaded to the order itself.
    delivery_id: int | None = None
