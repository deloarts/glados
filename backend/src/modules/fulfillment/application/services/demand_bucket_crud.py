"""
Shared use cases for the demand bucket catalogues of bought items, made
items and source items. The three families have the same create, update,
delete and read flow with the same permission gate, validation, error
messages and log texts; only the entity, result, mapper and exception types
differ. Each family subclasses these classes in its own use case package and
binds a `DemandBucketSpec`, so the per-family class names, constructor
signatures and `execute()` parameter names stay what endpoints, deps and
tests already use.

Buckets are display state, so none of these use cases publishes a domain
event; each write commits its unit of work once the repository write is done.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from typing import Generic
from typing import Protocol
from typing import TypeVar

from src.modules.fulfillment.application.dto.demand_bucket_dto import DemandBucketCommandBase
from src.modules.fulfillment.domain.services.demand_bucket_rules import DemandBucketRules
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class _DemandBucketEntity(Protocol):
    id: int
    name: str
    color: str


TEntity = TypeVar("TEntity", bound=_DemandBucketEntity)
TResult = TypeVar("TResult")
TFilter = TypeVar("TFilter")
TFilterIn = TypeVar("TFilterIn", contravariant=True)


class DemandBucketRepo(Protocol[TEntity, TFilterIn]):
    """The part of every family's bucket repository port these use cases call."""

    async def get_by_id(self, id: int, /) -> TEntity | None: ...

    async def get_by_name(self, name: str, /) -> TEntity | None: ...

    async def get_multi(self, filters: TFilterIn, /) -> tuple[int, list[TEntity]]: ...

    async def save(self, bucket: TEntity, /) -> TEntity: ...

    async def delete(self, bucket: TEntity, /) -> None: ...


@dataclass(frozen=True)
class DemandBucketSpec(Generic[TEntity, TResult]):
    """
    The types one demand family plugs into the shared use cases. `entity_cls`
    is a factory rather than `type[TEntity]` so the concrete dataclass can be
    passed without mypy matching it against the entity Protocol's constructor.
    """

    entity_cls: Callable[..., TEntity]
    to_result: Callable[[TEntity], TResult]
    not_found_error: type[Exception]
    already_exists_error: type[Exception]


class PaginatedBuckets(Generic[TResult]):
    def __init__(self, total: int, items: list[TResult]):
        self.total = total
        self.items = items


class _DemandBucketWrite(Generic[TEntity, TResult]):
    _spec: DemandBucketSpec[TEntity, TResult]

    def __init__(
        self,
        bucket_repo: DemandBucketRepo[TEntity, Any],
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._buckets = bucket_repo
        self._uow = uow

    async def _get_or_raise(self, bucket_id: int) -> TEntity:
        bucket = await self._buckets.get_by_id(bucket_id)
        if not bucket:
            raise self._spec.not_found_error(f"Bucket #{bucket_id} not found.")
        return bucket


class CreateDemandBucket(_DemandBucketWrite[TEntity, TResult]):
    async def execute(self, actor: User, cmd: DemandBucketCommandBase) -> TResult:
        DemandBucketRules.assert_can_write(actor)
        DemandBucketRules.assert_valid_color(cmd.color)
        name = DemandBucketRules.normalize_name(cmd.name)

        if await self._buckets.get_by_name(name):
            raise self._spec.already_exists_error(f"A bucket named {name!r} already exists.")

        bucket = self._spec.entity_cls(
            id=0,
            created=now_utc(),
            name=name,
            color=cmd.color,
            creator_id=actor.id,
        )
        saved = await self._buckets.save(bucket)
        await self._uow.commit()
        log.info(f"Created bucket {saved.name!r}, ID={saved.id}.")
        return self._spec.to_result(saved)


class UpdateDemandBucket(_DemandBucketWrite[TEntity, TResult]):
    async def execute(self, actor: User, bucket_id: int, cmd: DemandBucketCommandBase) -> TResult:
        """Renames and recolors a bucket. Name uniqueness is case-insensitive,
        so it is only re-checked when the normalized name changes beyond case."""
        DemandBucketRules.assert_can_write(actor)

        bucket = await self._get_or_raise(bucket_id)

        DemandBucketRules.assert_valid_color(cmd.color)
        name = DemandBucketRules.normalize_name(cmd.name)

        if name.lower() != bucket.name.lower():
            existing = await self._buckets.get_by_name(name)
            if existing and existing.id != bucket.id:
                raise self._spec.already_exists_error(f"A bucket named {name!r} already exists.")

        bucket.name = name
        bucket.color = cmd.color
        saved = await self._buckets.save(bucket)
        await self._uow.commit()
        log.info(f"Updated bucket {saved.name!r}, ID={saved.id}.")
        return self._spec.to_result(saved)


class DeleteDemandBucket(_DemandBucketWrite[TEntity, TResult]):
    async def execute(self, actor: User, bucket_id: int) -> TResult:
        """Hard-deletes a bucket. The repository nulls `bucket_id` on every
        demand it was assigned to in the same transaction; a demand's
        changelog is left untouched because buckets are display state."""
        DemandBucketRules.assert_can_write(actor)

        bucket = await self._get_or_raise(bucket_id)

        await self._buckets.delete(bucket)
        await self._uow.commit()
        log.info(f"Deleted bucket {bucket.name!r}, ID={bucket.id}.")
        return self._spec.to_result(bucket)


class GetDemandBucket(Generic[TEntity, TResult]):
    _spec: DemandBucketSpec[TEntity, TResult]

    def __init__(self, bucket_repo: DemandBucketRepo[TEntity, Any]) -> None:
        self._buckets = bucket_repo

    async def execute(self, bucket_id: int) -> TResult:
        bucket = await self._buckets.get_by_id(bucket_id)
        if not bucket:
            raise self._spec.not_found_error(f"Bucket #{bucket_id} not found.")
        return self._spec.to_result(bucket)


class GetDemandBuckets(Generic[TEntity, TResult, TFilter]):
    _spec: DemandBucketSpec[TEntity, TResult]

    def __init__(self, bucket_repo: DemandBucketRepo[TEntity, TFilter]) -> None:
        self._buckets = bucket_repo

    async def execute(self, filters: TFilter) -> PaginatedBuckets[TResult]:
        total, buckets = await self._buckets.get_multi(filters)
        return PaginatedBuckets(total=total, items=[self._spec.to_result(b) for b in buckets])
