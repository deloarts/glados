"""
Idempotency keys against the real schema: a claim inserts the key once per
user, a duplicate claim leaves the request's transaction usable, a
completed key replays its resources, a key reused for another request or
still open is refused, and the purge removes keys past their lifetime.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.models.idempotency_key_model import (
    IdempotencyKeyOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.repositories.idempotency_key_repository import (
    SqlAlchemyIdempotencyKeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.retention_purger import (
    SqlAlchemyRetentionPurger,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.services.idempotency import IdempotencyKeys
from src.modules.platform.application.services.idempotency import IdempotentRequest
from src.modules.platform.domain.entities.idempotency_key import ResourceRef
from src.modules.platform.domain.exceptions import IdempotencyKeyInFlightError
from src.modules.platform.domain.exceptions import IdempotencyKeyInvalidError
from src.modules.platform.domain.exceptions import IdempotencyKeyReusedError


@pytest.fixture
async def user_id(create_user) -> int:
    return (await create_user(username="keyholder", email="keyholder@example.com")).id


def _keys(db: AsyncSession) -> IdempotencyKeys:
    return IdempotencyKeys(SqlAlchemyIdempotencyKeyRepository(db), uow=SqlAlchemyUnitOfWork(db))


def _request(user_id: int, *, key: str = "k-1", request_hash: str = "h" * 64) -> IdempotentRequest:
    return IdempotentRequest(
        user_id=user_id, key=key, route="PUT /deliver", request_hash=request_hash
    )


async def test_a_completed_key_replays_the_resources_of_the_first_request(
    db: AsyncSession, user_id: int
) -> None:
    claim = await _keys(db).claim(_request(user_id))
    assert claim.record is not None
    await db.commit()
    await _keys(db).complete(claim, [ResourceRef("order_item", 7)])

    replay = await _keys(db).claim(_request(user_id))

    assert replay.record is None
    assert replay.replay == (ResourceRef("order_item", 7),)
    # The duplicate's savepoint rolled back alone; the session still works.
    assert await db.scalar(select(func.count()).select_from(IdempotencyKeyOrmModel)) == 1


async def test_a_key_still_open_answers_in_flight(db: AsyncSession, user_id: int) -> None:
    await _keys(db).claim(_request(user_id))
    await db.commit()

    with pytest.raises(IdempotencyKeyInFlightError):
        await _keys(db).claim(_request(user_id))


async def test_a_key_sent_with_another_request_is_refused(db: AsyncSession, user_id: int) -> None:
    claim = await _keys(db).claim(_request(user_id))
    await db.commit()
    await _keys(db).complete(claim, [])

    with pytest.raises(IdempotencyKeyReusedError):
        await _keys(db).claim(_request(user_id, request_hash="x" * 64))


async def test_a_failed_request_leaves_no_key(db: AsyncSession, user_id: int) -> None:
    await _keys(db).claim(_request(user_id))
    await db.rollback()

    claim = await _keys(db).claim(_request(user_id))

    assert claim.record is not None


async def test_the_same_key_of_another_user_is_their_own(
    db: AsyncSession, user_id: int, create_user
) -> None:
    other = (await create_user(username="other", email="other@example.com")).id
    await _keys(db).claim(_request(user_id))
    await db.commit()

    assert (await _keys(db).claim(_request(other))).record is not None


@pytest.mark.parametrize("key", ["", "x" * 256, "line\nbreak", "schlüssel"])
async def test_a_malformed_key_is_refused(db: AsyncSession, user_id: int, key: str) -> None:
    with pytest.raises(IdempotencyKeyInvalidError):
        await _keys(db).claim(_request(user_id, key=key))


async def test_the_purge_removes_keys_past_their_lifetime(db: AsyncSession, user_id: int) -> None:
    cutoff = datetime(2026, 7, 1, tzinfo=UTC)
    for key, created in (("old", cutoff - timedelta(hours=1)), ("new", cutoff)):
        db.add(
            IdempotencyKeyOrmModel(
                user_id=user_id,
                key=key,
                route="PUT /deliver",
                request_hash="h" * 64,
                status="completed",
                resources=[],
                created_at=created,
            )
        )
    await db.commit()

    removed = await SqlAlchemyRetentionPurger(db).purge_idempotency_keys_before(cutoff)

    assert removed == 1
    assert await db.scalar(select(IdempotencyKeyOrmModel.key)) == "new"
