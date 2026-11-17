"""
A retry that races its first request with the same Idempotency-Key: the
retry's claim waits on the key's unique index while the first request's
transaction is open, and once that commits it is answered from what the
first request wrote instead of claiming the key a second time.
"""

import asyncio

from sqlalchemy.ext.asyncio import AsyncEngine

from src.modules.platform.adapters.outbound.persistence.repositories.idempotency_key_repository import (
    SqlAlchemyIdempotencyKeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.services.idempotency import IdempotencyKeys
from src.modules.platform.application.services.idempotency import IdempotentRequest
from src.modules.platform.domain.entities.idempotency_key import ResourceRef
from tests.pg._floor import Floor
from tests.pg._race import sessions
from tests.pg._race import wait_for_lock
from tests.pg.conftest import RACE_B


async def test_a_concurrent_retry_waits_for_the_first_request_and_replays_it(
    floor: Floor, engine_a: AsyncEngine, engine_b: AsyncEngine, watcher: AsyncEngine
) -> None:
    request = IdempotentRequest(
        user_id=floor.actor.id, key="retry-1", route="PUT /deliver", request_hash="h" * 64
    )

    async with sessions(engine_a)() as first_db:
        first = IdempotencyKeys(
            SqlAlchemyIdempotencyKeyRepository(first_db), uow=SqlAlchemyUnitOfWork(first_db)
        )
        claim = await first.claim(request)
        assert claim.record is not None

        async def retry() -> object:
            async with sessions(engine_b)() as db:
                keys = IdempotencyKeys(
                    SqlAlchemyIdempotencyKeyRepository(db), uow=SqlAlchemyUnitOfWork(db)
                )
                return await keys.claim(request)

        retried = asyncio.create_task(retry())
        await wait_for_lock(watcher, RACE_B)
        # The first request records what it wrote and commits it with its key.
        await SqlAlchemyIdempotencyKeyRepository(first_db).mark_completed(
            claim.record.id, [ResourceRef("order_item", 5)], claim.record.created_at
        )
        await first_db.commit()

    answer = await retried
    assert getattr(answer, "record", "missing") is None
    assert getattr(answer, "replay", None) == (ResourceRef("order_item", 5),)
