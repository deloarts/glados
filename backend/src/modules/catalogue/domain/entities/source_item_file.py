"""
A file attached to a source item: metadata for a stored attachment,
including its category, content hash, and audit fields.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.catalogue.domain.value_objects.source_item_file_category import (
    SourceItemFileCategory,
)
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class SourceItemFile(Entity):
    source_item_id: int

    file_name: str
    stored_name: str
    mime_type: str
    size_bytes: int

    storage_path: str
    sha256: str

    category: SourceItemFileCategory

    created: datetime
    uploaded_by_user_id: int
