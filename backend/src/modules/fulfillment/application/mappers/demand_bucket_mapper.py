"""
Shared entity-to-result mapping for the bought-item, made-item, and
source-item demand bucket mappers. The three families' entities and
results differ only by type; the fields copied across are identical, so
each family's mapper class delegates its `to_result` body here and keeps
its own name for use cases and tests to import.
"""

from datetime import datetime
from typing import Protocol
from typing import TypeVar
from uuid import UUID

from src.modules.fulfillment.application.dto.demand_bucket_dto import DemandBucketResultBase


class _DemandBucketEntity(Protocol):
    id: int
    public_id: UUID
    created: datetime
    name: str
    color: str
    creator_id: int


TResult = TypeVar("TResult", bound=DemandBucketResultBase)


def demand_bucket_to_result(result_cls: type[TResult], entity: _DemandBucketEntity) -> TResult:
    return result_cls(
        id=entity.id,
        public_id=entity.public_id,
        created=entity.created,
        name=entity.name,
        color=entity.color,
        creator_id=entity.creator_id,
    )
