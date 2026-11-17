"""
An uploaded file attached to a made item, such as a drawing, datasheet, or
inspection report. Stored content lives in the storage adapter; this entity
tracks the metadata and the sha256 used to detect duplicate uploads.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class MadeItemFile(Entity):
    made_item_id: int

    file_name: str
    stored_name: str
    mime_type: str
    size_bytes: int

    storage_path: str
    sha256: str

    category: MadeItemFileCategory

    created: datetime
    uploaded_by_user_id: int
