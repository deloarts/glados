"""
File attachment metadata for bought items: name, storage location, hash,
mime type, and uploader audit trail.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class BoughtItemFile(Entity):
    bought_item_id: int

    file_name: str
    stored_name: str
    mime_type: str
    size_bytes: int

    storage_path: str
    sha256: str

    category: BoughtItemFileCategory

    created: datetime
    uploaded_by_user_id: int
