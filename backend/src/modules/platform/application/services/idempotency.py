"""
Idempotency keys for the web routes whose repetition would book something
twice, such as a delivery or a completion. A route that takes a key claims
it on the request's own session before its use case runs, so the key row is
the first thing the transaction writes and commits together with the work;
a request that fails leaves no key behind. A retry with the same key and
request finds the row and is answered from the resources the first request
wrote, which the route reads again, instead of being booked a second time.
A concurrent retry waits on the key's unique index until the first request
ends. The route holds back the commits of the use case and records what it
wrote (`complete`) in the same transaction, so the work, the key and its
record commit together, and a retry that finds the key finds it completed;
a key found still open, which only a request that committed its work
without the route's hold leaves, answers 409. Keys expire after
KEY_LIFETIME and are purged with the retention records.
"""

from dataclasses import dataclass
from datetime import timedelta

from src.modules.platform.domain.entities.idempotency_key import IdempotencyKey
from src.modules.platform.domain.entities.idempotency_key import IdempotencyKeyStatus
from src.modules.platform.domain.entities.idempotency_key import ResourceRef
from src.modules.platform.domain.exceptions import IdempotencyKeyInFlightError
from src.modules.platform.domain.exceptions import IdempotencyKeyInvalidError
from src.modules.platform.domain.exceptions import IdempotencyKeyReusedError
from src.modules.platform.ports.outbound.repositories.idempotency_key_repository import (
    IIdempotencyKeyRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc

KEY_LIFETIME = timedelta(hours=24)
MAX_KEY_LENGTH = 255


@dataclass(frozen=True)
class IdempotentRequest:
    """A request that carried an Idempotency-Key: who sent it, the key, the
    route it was sent to and a hash of its method, path, query and body."""

    user_id: int
    key: str
    route: str
    request_hash: str


@dataclass(frozen=True)
class Claim:
    """The outcome of claiming a key: `record` when this request goes ahead
    and books, `replay` the resources of the first request when it already
    completed."""

    record: IdempotencyKey | None = None
    replay: tuple[ResourceRef, ...] | None = None


def assert_valid_key(key: str) -> None:
    if not key or len(key) > MAX_KEY_LENGTH or not key.isprintable() or not key.isascii():
        raise IdempotencyKeyInvalidError(
            f"An Idempotency-Key is 1 to {MAX_KEY_LENGTH} printable ASCII characters."
        )


class IdempotencyKeys:
    def __init__(self, repo: IIdempotencyKeyRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def claim(self, request: IdempotentRequest) -> Claim:
        """Claims the key for this request, or answers how the first request
        with it ended: a replay of what it wrote, IdempotencyKeyReusedError
        when that request was a different one, and
        IdempotencyKeyInFlightError while it has not finished."""
        assert_valid_key(request.key)
        record = IdempotencyKey(
            id=0,
            user_id=request.user_id,
            key=request.key,
            route=request.route,
            request_hash=request.request_hash,
            status=IdempotencyKeyStatus.OPEN,
            created_at=now_utc(),
        )
        if await self._repo.claim(record):
            return Claim(record=record)
        first = await self._repo.get_by_user_and_key(request.user_id, request.key)
        if first is None:
            # The first request's key expired and was purged in between.
            raise IdempotencyKeyInFlightError(
                "The first request with this Idempotency-Key just ended; try again."
            )
        if (first.route, first.request_hash) != (request.route, request.request_hash):
            raise IdempotencyKeyReusedError(
                "This Idempotency-Key was already used for a different request; send a new "
                "key for a new action."
            )
        if first.status is IdempotencyKeyStatus.OPEN:
            raise IdempotencyKeyInFlightError(
                "The first request with this Idempotency-Key is still being processed; try "
                "again shortly."
            )
        return Claim(replay=tuple(first.resources))

    async def complete(self, claim: Claim, resources: list[ResourceRef]) -> None:
        """Records what the claimed request wrote and commits, which commits
        the work the route held back with it, so a retry can be answered
        from it."""
        if claim.record is None:
            return
        await self._repo.mark_completed(claim.record.id, resources, now_utc())
        await self._uow.commit()
