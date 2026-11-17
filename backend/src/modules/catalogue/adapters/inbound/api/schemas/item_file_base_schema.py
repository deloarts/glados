"""
Shared response fields for the bought item, made item, source item, and
product file schemas: everything about a stored file except the parent-id
field (each item type names it differently), the category enum (each item
type has its own), and any item-type-specific extra field.
"""

from datetime import datetime

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse


class ItemFileResponseBase(EntityResponse):
    file_name: str
    stored_name: str
    mime_type: str
    size_bytes: int
    storage_path: str
    sha256: str
    created: datetime
    uploaded_by_user_id: int
    url: str | None
