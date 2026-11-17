"""
An uploaded file attached to a product, such as a specification or
certificate. Stored content lives in the storage adapter; this entity
tracks the metadata and the sha256 used to detect duplicate uploads.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class ProductFile(Entity):
    product_id: int

    file_name: str
    stored_name: str
    mime_type: str
    size_bytes: int

    storage_path: str
    sha256: str

    category: ProductFileCategory

    created: datetime
    uploaded_by_user_id: int
