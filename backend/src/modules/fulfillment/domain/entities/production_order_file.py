"""
A file attached to a production order: metadata for a stored attachment,
including its category, content hash, and audit fields.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.fulfillment.domain.value_objects.production_order_file_category import (
    ProductionOrderFileCategory,
)
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class ProductionOrderFile(Entity):
    production_order_id: int

    file_name: str
    stored_name: str
    mime_type: str
    size_bytes: int

    storage_path: str
    sha256: str

    category: ProductionOrderFileCategory

    created: datetime
    uploaded_by_user_id: int
