"""
Resolves a public_id to the resource type + internal id that owns it, by
probing every registered aggregate, one indexed lookup per table, combined
into a single UNION ALL query so resolution costs one round-trip regardless
of how many tables are registered.

Deliberately does NOT reuse change_tracking.MODEL_TOPICS: that registry
folds child rows (lot positions, lot steps, ...) into their parent's
live-sync topic, which is right for refetch signalling but wrong here, a
scanned lot-position tag must resolve to the position itself, not its lot.

Scoped to resources with a standalone `GET /{resource}/{id}` endpoint,
enough for a QR scan to route straight to a page. Every mapped table still
carries a public_id regardless of whether it's registered here; a new
resource is registered by its module in src/bootstrap/registrations.py.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import literal
from sqlalchemy import select
from sqlalchemy import union_all
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.ports.outbound.repositories.public_id_resolver import ResolvedPublicId

# The aggregates a public id may name, with their resource path segment.
# Each module registers its own at startup through
# src/bootstrap/registrations.py.
_REGISTRY: dict[type[Any], str] = {}


def register_public_id_models(models: dict[type[Any], str]) -> None:
    """Adds aggregates a scanned or shared public id may resolve to. Each
    model needs an `id` and a `public_id` column."""
    _REGISTRY.update(models)


class SqlAlchemyPublicIdResolver:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def resolve(self, public_id: UUID) -> ResolvedPublicId | None:
        selects = []
        for model, resource in _REGISTRY.items():
            stmt = select(literal(resource).label("resource"), model.id.label("id")).where(
                model.public_id == public_id
            )
            # `archived` rows (unlike `deleted` ones, e.g. Project) are
            # deliberately NOT filtered out here: a scanned tag on an
            # archived row must still resolve, matching every `GET /{id}`
            # endpoint's "regardless of archived" contract.
            if hasattr(model, "deleted"):
                stmt = stmt.where(model.deleted.is_(False))
            selects.append(stmt)

        row = (await self._db.execute(union_all(*selects).limit(1))).first()
        return ResolvedPublicId(resource=row.resource, id=row.id) if row else None
