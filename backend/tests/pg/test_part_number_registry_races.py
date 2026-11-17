"""
A made-item revision that keeps its part number and a release of that number
at once, on a real Postgres. Both read the registry row FOR UPDATE, so the
second waits for the first: a release that comes second counts the item the
revision committed and keeps the entry, and a revision that comes second
finds the entry gone and claims the number again. Either way the item never
carries a number without its registry entry.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.part_number_registry_model import (
    PartNumberRegistryOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.part_number_registry_repository import (
    SqlAlchemyPartNumberRegistryRepository,
)
from tests.integration.repository_reads._graph import NOW
from tests.pg._floor import Floor
from tests.pg._race import WAIT_SECONDS
from tests.pg._race import outcomes
from tests.pg._race import sessions
from tests.pg._race import start
from tests.pg._race import wait_for_lock
from tests.pg.conftest import RACE_B

_NUMBER = "PN-RACE-1"


async def _revise(
    engine: AsyncEngine,
    creator_id: int,
    held: asyncio.Event | None = None,
    release: asyncio.Event | None = None,
) -> None:
    """Makes sure the number is registered to made items and saves a
    revision carrying it, as a revision that keeps its family's number does;
    with the events, holds the registry row until `release` is set."""
    async with sessions(engine)() as db:
        await SqlAlchemyPartNumberRegistryRepository(db).assert_family(_NUMBER, "made")
        if held is not None and release is not None:
            held.set()
            await asyncio.wait_for(release.wait(), WAIT_SECONDS * 2)
        db.add(
            MadeItemOrmModel(
                created=NOW,
                changed=NOW,
                changes=[],
                revision="B",
                article_name="Bracket",
                status="active",
                data_source="WEB",
                part_number=_NUMBER,
                creator_id=creator_id,
            )
        )
        await db.commit()


async def _release(
    engine: AsyncEngine, held: asyncio.Event | None = None, release: asyncio.Event | None = None
) -> None:
    """Releases the number if nothing carries it; with the events, holds the
    registry row until `release` is set."""
    async with sessions(engine)() as db:
        await SqlAlchemyPartNumberRegistryRepository(db).release_if_unused(_NUMBER)
        if held is not None and release is not None:
            held.set()
            await asyncio.wait_for(release.wait(), WAIT_SECONDS * 2)
        await db.commit()


async def _registered_kind(engine: AsyncEngine) -> str | None:
    async with sessions(engine)() as db:
        kind: str | None = await db.scalar(
            select(PartNumberRegistryOrmModel.kind).where(
                PartNumberRegistryOrmModel.part_number == _NUMBER
            )
        )
        return kind


async def _registered(floor: Floor) -> None:
    await SqlAlchemyPartNumberRegistryRepository(floor.db).claim(_NUMBER, "made")
    await floor.db.commit()


async def test_a_release_waits_for_the_revision_and_keeps_its_entry(
    floor: Floor, engine_a: AsyncEngine, engine_b: AsyncEngine, watcher: AsyncEngine
) -> None:
    await _registered(floor)
    held, release = asyncio.Event(), asyncio.Event()
    first = start(_revise(engine_a, floor.actor.id, held, release))
    second = None
    try:
        await asyncio.wait_for(held.wait(), WAIT_SECONDS)
        second = start(_release(engine_b))
        await wait_for_lock(watcher, RACE_B)
    finally:
        release.set()
    await outcomes(first, second)

    assert await _registered_kind(engine_a) == "made"


async def test_a_revision_after_a_release_claims_the_number_again(
    floor: Floor, engine_a: AsyncEngine, engine_b: AsyncEngine, watcher: AsyncEngine
) -> None:
    await _registered(floor)
    held, release = asyncio.Event(), asyncio.Event()
    first = start(_release(engine_a, held, release))
    second = None
    try:
        await asyncio.wait_for(held.wait(), WAIT_SECONDS)
        second = start(_revise(engine_b, floor.actor.id))
        await wait_for_lock(watcher, RACE_B)
    finally:
        release.set()
    await outcomes(first, second)

    assert await _registered_kind(engine_a) == "made"
