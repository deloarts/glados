"""
The merge targets of a catalogue item are the catalogue search's matches
without the item itself, each with the merge rule's verdict: an archived or
inactive target is refused with its reason, an active one is allowed, and
one the item had replaced is allowed and becomes active again.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from tests.integration.test_api_catalogue_merges import _settings  # noqa: F401
from tests.integration.test_api_catalogue_merges import _supplier

BOUGHT = "/api/v1/web/bought-items"
MADE = "/api/v1/web/made-items"


def _verdicts(response: Any) -> dict[int, tuple[str | None, bool]]:
    assert response.status_code == 200, response.text
    return {row["item"]["id"]: (row["refusal"], row["reactivates"]) for row in response.json()}


async def _shape(db: AsyncSession, model: type[Any], ids: dict[str, int], source_id: int) -> None:
    """Makes the targets inactive, archived and replaced by the source."""
    inactive = await db.get(model, ids["inactive"])
    inactive.status = "inactive"
    archived = await db.get(model, ids["archived"])
    archived.archived = True
    replaced = await db.get(model, ids["replaced"])
    replaced.status = "replaced"
    replaced.successor_item_id = source_id
    await db.commit()


async def test_bought_merge_targets_carry_the_merge_verdict(auth_client, db) -> None:
    client = await auth_client(permissions=["write:bought_items", "write:suppliers"])
    supplier = await _supplier(client)
    ids: dict[str, int] = {}
    for name in ("source", "active", "inactive", "archived", "replaced"):
        created = await client.post(
            f"{BOUGHT}/",
            json={
                "order_code_1": f"MT-{name}",
                "article_name": f"Merge {name}",
                "manufacturer_id": supplier,
            },
        )
        assert created.status_code == 201, created.text
        ids[name] = created.json()["id"]
    await _shape(db, BoughtItemOrmModel, ids, ids["source"])

    verdicts = _verdicts(
        await client.get(f"{BOUGHT}/{ids['source']}/merge-targets", params={"search": "Merge"})
    )

    assert verdicts == {
        ids["active"]: (None, False),
        ids["inactive"]: ("not_active", False),
        ids["archived"]: ("archived", False),
        ids["replaced"]: (None, True),
    }


async def test_made_merge_targets_carry_the_merge_verdict(auth_client, db) -> None:
    client = await auth_client(permissions=["write:made_items"])
    ids: dict[str, int] = {}
    for name in ("source", "active", "inactive", "archived", "replaced"):
        created = await client.post(
            f"{MADE}/", json={"revision": "A", "article_name": f"Merge {name}"}
        )
        assert created.status_code == 201, created.text
        ids[name] = created.json()["id"]
    await _shape(db, MadeItemOrmModel, ids, ids["source"])

    verdicts = _verdicts(
        await client.get(f"{MADE}/{ids['source']}/merge-targets", params={"search": "Merge"})
    )

    assert verdicts == {
        ids["active"]: (None, False),
        ids["inactive"]: ("not_active", False),
        ids["archived"]: ("archived", False),
        ids["replaced"]: (None, True),
    }


async def test_merge_targets_of_an_unknown_item_are_not_found(auth_client) -> None:
    client = await auth_client(permissions=[])

    missing = await client.get(f"{BOUGHT}/999999/merge-targets")

    assert missing.status_code == 404, missing.text
