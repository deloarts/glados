"""
Wire schema for GET /web/pdm/preview. Mirrors application.dto.
pdm_preview_dto field for field; kept separate per the DTO/schema
distinction (see the backend skill), even though the two shapes are
currently identical.
"""

from datetime import datetime
from uuid import UUID

from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class PdmPreviewFileResponse(ResponseModel):
    file_id: int
    name: str
    path: str
    part_number: str
    revision: str | None
    article_name: str | None
    version: int
    state: str
    modified_at: datetime | None
    sync_state: str
    last_error: str | None


class PdmPreviewNewerResponse(ResponseModel):
    item_id: int
    item_public_id: UUID
    part_number: str
    revision: str | None
    file_id: int
    name: str
    version: int
    state: str
    modified_at: datetime | None


class PdmPreviewResponse(ResponseModel):
    kind: str
    enabled: bool
    unlinked: list[PdmPreviewFileResponse]
    newer: list[PdmPreviewNewerResponse]
