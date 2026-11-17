"""
DTOs for resolving public IDs to internal resource identifiers.
"""

from uuid import UUID

from src.modules.platform.application.dto.base import ResultModel


class ResolvePublicIdResult(ResultModel):
    resource: str
    id: int
    public_id: UUID
