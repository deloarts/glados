"""
Resolves an opaque public_id to the resource kind and internal id it points to, so a client
holding only a public_id (a shared link, for example) can find out what it identifies without
already knowing which entity type it belongs to.
"""

from uuid import UUID

from src.modules.platform.application.dto.resolve_dto import ResolvePublicIdResult
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.exceptions import PublicIdNotFoundError
from src.modules.platform.ports.outbound.repositories.public_id_resolver import IPublicIdResolver


class ResolvePublicId:
    def __init__(self, resolver: IPublicIdResolver) -> None:
        self._resolver = resolver

    async def execute(self, public_id: UUID) -> ResolvePublicIdResult:
        resolved = found_or_raise(
            await self._resolver.resolve(public_id),
            PublicIdNotFoundError,
            f"public_id {public_id} not found.",
        )
        return ResolvePublicIdResult(
            resource=resolved.resource, id=resolved.id, public_id=public_id
        )
