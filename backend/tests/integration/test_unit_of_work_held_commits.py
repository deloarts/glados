"""
A held commit and what waits for it: while an Idempotency-Key route holds
the session's commits, an effect that must follow the commit, such as the
schedule recompute's request, waits for the commit that ends the hold, runs
once after it, and is dropped when the work rolls back instead.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.unit_of_work import RollbackWhileHeldError
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.adapters.outbound.persistence.unit_of_work import hold_commits
from src.modules.platform.ports.outbound.unit_of_work_port import IDeferringUnitOfWork


def _recorder() -> tuple[list[str], object]:
    ran: list[str] = []

    async def effect() -> None:
        ran.append("effect")

    return ran, effect


async def test_an_effect_without_a_hold_is_not_deferred(db: AsyncSession) -> None:
    uow = SqlAlchemyUnitOfWork(db)
    _, effect = _recorder()

    assert isinstance(uow, IDeferringUnitOfWork)
    assert uow.defer_until_committed(effect) is False  # type: ignore[arg-type]


async def test_a_held_effect_runs_once_after_the_commit_that_ends_the_hold(
    db: AsyncSession,
) -> None:
    uow = SqlAlchemyUnitOfWork(db)
    ran, effect = _recorder()

    async with hold_commits(db):
        assert uow.defer_until_committed(effect) is True  # type: ignore[arg-type]
        await uow.commit()
        assert ran == []
    assert ran == []

    await uow.commit()
    assert ran == ["effect"]
    await uow.commit()
    assert ran == ["effect"]


async def test_a_held_effect_is_dropped_when_the_work_rolls_back(db: AsyncSession) -> None:
    uow = SqlAlchemyUnitOfWork(db)
    ran, effect = _recorder()

    async with hold_commits(db):
        uow.defer_until_committed(effect)  # type: ignore[arg-type]
    await uow.rollback()
    await uow.commit()

    assert ran == []


async def test_a_held_effect_is_dropped_when_the_held_work_raises(db: AsyncSession) -> None:
    uow = SqlAlchemyUnitOfWork(db)
    ran, effect = _recorder()

    with pytest.raises(RuntimeError):
        async with hold_commits(db):
            uow.defer_until_committed(effect)  # type: ignore[arg-type]
            raise RuntimeError("the use case failed")
    await uow.commit()

    assert ran == []


async def test_a_failing_effect_does_not_undo_the_commit_or_stop_the_others(
    db: AsyncSession,
) -> None:
    uow = SqlAlchemyUnitOfWork(db)
    ran: list[str] = []

    async def failing() -> None:
        raise RuntimeError("redis down")

    async def second() -> None:
        ran.append("second")

    async with hold_commits(db):
        uow.defer_until_committed(failing)
        uow.defer_until_committed(second)
    await uow.commit()

    assert ran == ["second"]


async def test_work_that_rolls_back_inside_a_hold_and_carries_on_is_refused(
    db: AsyncSession,
) -> None:
    uow = SqlAlchemyUnitOfWork(db)
    ran, effect = _recorder()

    with pytest.raises(RollbackWhileHeldError):
        async with hold_commits(db):
            uow.defer_until_committed(effect)  # type: ignore[arg-type]
            await uow.rollback()
    await uow.commit()

    assert ran == []


async def test_work_that_rolls_back_inside_a_hold_and_raises_keeps_its_error(
    db: AsyncSession,
) -> None:
    uow = SqlAlchemyUnitOfWork(db)

    with pytest.raises(LookupError):
        async with hold_commits(db):
            await uow.rollback()
            raise LookupError("the work's own refusal")
    async with hold_commits(db):
        await uow.commit()
