"""
Two transactions that draw a number of the same prefix at once, on a real
Postgres: the second waits for the first's counter row and then counts on
it, whether the first created the counter or found it, so both numbers are
distinct and the second follows the first.
"""

import asyncio
from datetime import date

from sqlalchemy.ext.asyncio import AsyncEngine

from src.modules.catalogue.adapters.outbound.persistence.models.part_number_registry_model import (
    PartNumberRegistryOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.number_counters import NumberFamily
from src.modules.platform.adapters.outbound.persistence.number_counters import draw_number
from tests.pg._race import WAIT_SECONDS
from tests.pg._race import outcomes
from tests.pg._race import sessions
from tests.pg._race import start
from tests.pg._race import wait_for_lock
from tests.pg.conftest import RACE_B

_TODAY = date(2026, 10, 25)


async def _draw(
    engine: AsyncEngine, drawn: asyncio.Event | None = None, release: asyncio.Event | None = None
) -> str:
    """Draws one number and commits; with the events, signals the draw and
    holds the counter row until `release` is set."""
    async with sessions(engine)() as db:
        number = await draw_number(
            db,
            NumberFamily.LOT,
            "R-{seq:03d}",
            column=PartNumberRegistryOrmModel.part_number,
            today=_TODAY,
        )
        if drawn is not None and release is not None:
            drawn.set()
            await asyncio.wait_for(release.wait(), WAIT_SECONDS * 2)
        await db.commit()
        return number


async def _race(engine_a: AsyncEngine, engine_b: AsyncEngine, watcher: AsyncEngine) -> list[str]:
    drawn, release = asyncio.Event(), asyncio.Event()
    first = start(_draw(engine_a, drawn, release))
    second = None
    try:
        await asyncio.wait_for(drawn.wait(), WAIT_SECONDS)
        second = start(_draw(engine_b))
        await wait_for_lock(watcher, RACE_B)
    finally:
        release.set()
    return await outcomes(first, second)


async def test_two_first_draws_of_a_prefix_get_distinct_numbers_in_order(
    engine_a: AsyncEngine, engine_b: AsyncEngine, watcher: AsyncEngine
) -> None:
    assert await _race(engine_a, engine_b, watcher) == ["R-001", "R-002"]


async def test_two_draws_on_an_existing_counter_get_distinct_numbers_in_order(
    engine_a: AsyncEngine, engine_b: AsyncEngine, watcher: AsyncEngine
) -> None:
    assert await _draw(engine_a) == "R-001"

    assert await _race(engine_a, engine_b, watcher) == ["R-002", "R-003"]
