"""
The bought-item batch create end to end: references resolved by name, an
existing item found by its normalised order code and reported with its
divergences instead of imported, in-file duplicates, invalid rows, the row
limit, and a commit that creates only the ready rows and persists them.
"""

from typing import Any

import pytest

from src.bootstrap.adapters.outbound.persistence.admin_settings_seed import _data_import_defaults
from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.domain.entities.admin_settings.data_import import DataImportProfile
from src.modules.catalogue.domain.events.bought_item_events import BoughtItemCreated
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration.repository_reads._graph import Graph

IMPORT = f"{API_WEB}/bought-items-import"
ITEMS = f"{API_WEB}/bought-items"


@pytest.fixture
async def buyer(auth_client) -> Any:
    return await auth_client(
        username="buyer", email="buyer@example.com", permissions=[Permission.WRITE_BOUGHT_ITEMS]
    )


@pytest.fixture
async def graph(db, create_user) -> Graph:
    """The Acme supplier, the Fasteners article group, the Cylinders product
    family and one existing Acme item with order code OC-1."""
    user = await create_user(username="owner", email="owner@example.com")
    other = await create_user(username="other", email="other@example.com")
    graph = Graph(db, user, other)
    await graph.bought_item()
    await SqlAlchemyAdminSettingsRepository(db).save_data_import(_data_import_defaults())
    await db.commit()
    return graph


def _row(index: int, **fields: Any) -> dict[str, Any]:
    return {
        "row_index": index,
        "article_name": "Cylinder DSNU-20",
        "order_code_1": f"NEW-{index}",
        "manufacturer_name": "acme",
        **fields,
    }


async def _validate(client: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    response = await client.post(f"{IMPORT}/validate", json={"rows": rows})
    assert response.status_code == 200, response.text
    return list(response.json()["results"])


async def test_import_ready_row_resolves_references_by_name(buyer, graph: Graph) -> None:
    [result] = await _validate(
        buyer,
        [_row(0, article_group_names="fasteners; ", product_family_name=" CYLINDERS ", mass=250)],
    )

    assert result["row_status"] == "ready", result
    assert result["resolved_manufacturer_id"] == (await graph.supplier()).id
    assert result["resolved_article_group_ids"] == [(await graph.article_group()).id]
    assert result["resolved_product_family_id"] == (await graph.product_family()).id


async def test_import_existing_item_is_reported_not_imported(buyer, graph: Graph) -> None:
    [result] = await _validate(
        buyer, [_row(0, order_code_1=" oc 1 ", article_name="Other name", tariff_number="8481")]
    )

    assert result["row_status"] == "exists"
    assert result["existing_item"]["id"] == (await graph.bought_item()).id
    fields = {d["field"]: d for d in result["divergences"]}
    assert fields["article_name"]["db_value"] == "Screw M6"
    assert fields["article_name"]["file_value"] == "Other name"
    assert "tariff_number" in fields


async def test_import_flags_duplicates_unknown_references_and_bad_rows(buyer, graph: Graph) -> None:
    results = await _validate(
        buyer,
        [
            _row(0, order_code_1="X-1"),
            _row(1, order_code_1="x1"),
            _row(2, manufacturer_name="Nobody"),
            _row(3, article_group_names="Unknown group"),
            _row(4, product_family_name="Unknown family"),
            _row(5, article_name=" "),
            _row(6, mass=1.5),
        ],
    )

    assert [r["row_status"] for r in results] == [
        "ready",
        "duplicate_in_file",
        "unresolved_reference",
        "unresolved_reference",
        "unresolved_reference",
        "invalid",
        "invalid",
    ]
    assert "Nobody" in results[2]["errors"][0]


async def test_import_commit_creates_only_ready_rows(
    buyer, graph: Graph, published_events: list[object]
) -> None:
    response = await buyer.post(
        f"{IMPORT}/commit",
        json={
            "rows": [
                _row(0, product_family_name="Cylinders"),
                _row(1, order_code_1="OC-1"),
                _row(2, manufacturer_name="Nobody"),
                _row(3, order_code_1="NEW-3b", gtin="4006381333948"),
            ]
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created_row_indexes"] == [0, 3]
    assert len(body["created_item_ids"]) == 2
    reread = await buyer.get(f"{ITEMS}/{body['created_item_ids'][0]}")
    assert reread.json()["product_family"]["name"] == "Cylinders"
    assert sum(isinstance(e, BoughtItemCreated) for e in published_events) == 2


async def test_import_refuses_more_rows_than_the_profile_allows(buyer, graph: Graph, db) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    settings = await repo.get_data_import()
    settings.profiles["bought_item_create"] = DataImportProfile(max_rows=1)
    await repo.save_data_import(settings)
    await db.commit()

    response = await buyer.post(f"{IMPORT}/validate", json={"rows": [_row(0), _row(1)]})

    assert response.status_code == 400
    assert response.json()["code"] == "DataImportRowLimitExceededError"


async def test_import_needs_the_create_permission(auth_client, graph: Graph) -> None:
    reader = await auth_client(permissions=[], username="reader", email="reader@example.com")

    response = await reader.post(f"{IMPORT}/validate", json={"rows": [_row(0)]})

    assert response.status_code == 403
