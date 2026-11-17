"""
The fuzzy tier of the global search on a real Postgres. It calls pg_trgm's
similarity(), which only Postgres has; the integration suite runs on SQLite
with a Python stand-in registered in tests/integration/conftest.py, so only
these tests prove the SQL the repository sends works where it runs in
production. The schema here comes from the models, not the migrations, so
the fixture creates the pg_trgm extension the way the initial migration
does.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy import text

from src.modules.workspace.adapters.outbound.persistence.repositories.product_repository import (
    SqlAlchemyProductRepository,
)
from src.modules.workspace.domain.entities.product import Product
from src.read.adapters.outbound.persistence.repositories.global_search_repository import (
    SqlAlchemyGlobalSearchRepository,
)
from src.read.ports.outbound.repositories.global_search_repository import SEARCH_RESOURCES
from src.read.ports.outbound.repositories.global_search_repository import SearchGroup
from tests.integration.repository_reads._graph import NOW
from tests.pg._floor import Floor


@pytest.fixture(autouse=True)
def _trigram(schema_engine: Engine) -> Iterator[None]:
    """The extension stays after the test: dropping tables leaves it, and
    creating it again is a no-op."""
    with schema_engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    yield


async def save_product(floor: Floor, number: str, *, archived: bool = False) -> None:
    customer = await floor.graph.customer()
    await SqlAlchemyProductRepository(floor.db).save(
        Product(
            id=0,
            created=NOW,
            product_number=number,
            archived=archived,
            customer_id=customer.id,
            designated_user_id=floor.actor.id,
            creator_id=floor.actor.id,
        )
    )
    await floor.db.commit()


def _group(groups: list[SearchGroup], resource: str) -> SearchGroup:
    return next(group for group in groups if group.resource == resource)


async def test_a_typo_finds_the_product_through_the_fuzzy_tier(floor: Floor) -> None:
    await save_product(floor, "GEARBOX-4711")
    await save_product(floor, "GEARBOX-4712", archived=True)
    await save_product(floor, "SPINDLE-0815")

    groups = await SqlAlchemyGlobalSearchRepository(floor.db).search("GEARBX-4711", 10)

    products = _group(groups, "products")
    assert [(hit.label, hit.match_kind) for hit in products.items] == [("GEARBOX-4711", "fuzzy")]
    # The total counts the ranked tiers only; a fuzzy hit never matched the
    # term itself.
    assert products.total == 0


async def test_fuzzy_hits_top_up_the_ranked_page_without_repeating_it(floor: Floor) -> None:
    await save_product(floor, "GEARBOX-4711")
    await save_product(floor, "GEARBOX-4711-B")
    await save_product(floor, "GEARBOX-4712")

    repo = SqlAlchemyGlobalSearchRepository(floor.db)
    page = _group(await repo.search("GEARBOX-4711", 10), "products")
    full_ranked_page = _group(await repo.search("GEARBOX-4711", 2), "products")

    assert [(hit.label, hit.match_kind) for hit in page.items] == [
        ("GEARBOX-4711", "exact"),
        ("GEARBOX-4711-B", "prefix"),
        ("GEARBOX-4712", "fuzzy"),
    ]
    assert page.total == 2
    # A page the ranked tiers fill on their own runs no fuzzy query.
    assert [hit.match_kind for hit in full_ranked_page.items] == ["exact", "prefix"]


async def test_every_resource_runs_its_fuzzy_query(floor: Floor) -> None:
    """A term no row contains leaves every ranked page empty, so each
    resource sends its fuzzy query, and Postgres must accept all of them;
    a term this unlike every seeded number returns nothing."""
    graph = floor.graph
    await graph.full_lot()
    await graph.bought_order_item()
    await graph.calculation()
    await graph.checklist()

    groups = await SqlAlchemyGlobalSearchRepository(floor.db).search("qqxzqq", 10)

    assert [group.resource for group in groups] == list(SEARCH_RESOURCES)
    assert {group.resource: group.items for group in groups if group.items} == {}
