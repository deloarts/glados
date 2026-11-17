"""
The `/changelog` routes of the web API: each serves the stored changelog
lines of its row through its get use case, and every one of them answers 404
for an id that does not exist.
"""

import dataclasses
from typing import Any

import pytest

from src.modules.catalogue.adapters.outbound.persistence.repositories.supplier_repository import (
    SqlAlchemySupplierRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.platform.const import API_WEB
from tests.integration.repository_reads._graph import Graph

_MISSING_ID = 999_999

CHANGELOG_COLLECTIONS = [
    "suppliers",
    "article-groups",
    "product-families",
    "fabrication-methods",
    "inspection-methods",
    "source-item-types",
    "bought-items-demands",
    "made-items-demands",
    "production-lots",
    "bought-items",
    "made-items",
    "source-items",
    "projects",
    "quote-requests",
]


@pytest.fixture
async def reader(auth_client) -> Any:
    return await auth_client(username="reader", email="reader@example.com")


@pytest.fixture
async def graph(db, create_user) -> Graph:
    user = await create_user(username="owner", email="owner@example.com")
    other = await create_user(username="other", email="other@example.com")
    return Graph(db, user, other)


@pytest.mark.parametrize("collection", CHANGELOG_COLLECTIONS)
async def test_changelog_of_a_missing_id_is_404(reader: Any, collection: str) -> None:
    response = await reader.get(f"{API_WEB}/{collection}/{_MISSING_ID}/changelog")
    assert response.status_code == 404, response.text


async def test_supplier_changelog_returns_the_stored_lines(reader: Any, graph: Graph) -> None:
    repo = SqlAlchemySupplierRepository(graph.db)
    supplier = await graph.supplier()
    await repo.save(dataclasses.replace(supplier, changes=["Created.", "Renamed."]))
    await graph.db.commit()

    response = await reader.get(f"{API_WEB}/suppliers/{supplier.id}/changelog")

    assert response.status_code == 200, response.text
    assert response.json() == ["Created.", "Renamed."]


async def test_lot_changelog_returns_the_stored_lines(reader: Any, graph: Graph) -> None:
    repo = SqlAlchemyProductionLotRepository(graph.db)
    lot = await graph.lot()
    await repo.save(dataclasses.replace(lot, changes=["Created."]))
    await graph.db.commit()

    response = await reader.get(f"{API_WEB}/production-lots/{lot.id}/changelog")

    assert response.status_code == 200, response.text
    assert response.json() == ["Created."]
