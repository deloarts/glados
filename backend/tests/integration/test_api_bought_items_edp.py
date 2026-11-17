"""
The EPLAN Data Portal on single bought items, against a fake portal: the
create dialog's search (values filled, existing item found), a create that
carries the portal link, and the lookup on an item with its comparison,
candidates and the apply action, which writes the chosen fields on a web
row and only links a PDM-owned row's locked fields.
"""

from dataclasses import dataclass
from dataclasses import replace
from typing import Any

import pytest

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.catalogue.domain.events.bought_item_events import BoughtItemEdpPictureRequested
from src.modules.external_data.adapters.inbound.api.deps.services import (
    get_eplan_data_portal_factory,
)
from src.modules.external_data.domain.entities.admin_settings.eplan_data_portal import (
    AdminEdpSettings,
)
from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpNumberMatch
from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpPart
from src.modules.external_data.ports.outbound.eplan_data_portal_port import EdpConnection
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._edit_versions import row_version

EDP = f"{API_WEB}/bought-items-edp"
ITEMS = f"{API_WEB}/bought-items"


def _part(part_id: int, order: str, code: str = "FES") -> EdpPart:
    return EdpPart(
        part_id=part_id,
        part_number=f"{code}.{order}",
        order_number=order,
        type_number=f"DSNU-{order}",
        designation={"de_DE": f"Zylinder {order}"},
        manufacturer_code=code,
        manufacturer_name="Festo",
        product_groups=("Fluid power", "Cylinders"),
        support_url=f"https://support.example.test/{order}",
    )


PARTS = {1: _part(1, "19210"), 2: _part(2, "19211"), 3: _part(3, "19211", code="OTH")}


@dataclass
class _FakePortal:
    def factory(self, connection: EdpConnection) -> "_FakePortal":
        return self

    async def search(self, query: str, limit: int) -> list[EdpPart]:
        return [PARTS[1], PARTS[2]][:limit]

    async def check_numbers(self, numbers: list[str]) -> list[EdpNumberMatch]:
        table = {"19210": (1,), "19211": (2, 3)}
        return [EdpNumberMatch(search=n, part_ids=table.get(n, ())) for n in numbers]

    async def get_parts(self, part_ids: list[int]) -> list[EdpPart]:
        return [PARTS[i] for i in part_ids if i in PARTS]


@pytest.fixture(autouse=True)
def portal() -> Any:
    fake = _FakePortal()
    app.dependency_overrides[get_eplan_data_portal_factory] = lambda: fake.factory
    yield fake
    app.dependency_overrides.pop(get_eplan_data_portal_factory, None)


@pytest.fixture
async def buyer(auth_client) -> Any:
    return await auth_client(
        username="buyer",
        email="buyer@example.com",
        permissions=[
            Permission.WRITE_BOUGHT_ITEMS,
            Permission.USE_DATA_PORTAL,
            Permission.WRITE_SUPPLIERS,
            Permission.WRITE_ARTICLE_GROUPS,
        ],
    )


@pytest.fixture
async def festo(buyer, db) -> int:
    supplier = (
        await buyer.post(f"{API_WEB}/suppliers/", json={"name": "Festo SE", "edp_code": "FES"})
    ).json()
    await buyer.post(f"{API_WEB}/product-families/", json={"name": "Cylinders"})
    await SqlAlchemyAdminSettingsRepository(db).save_edp(
        AdminEdpSettings(id=1, enabled=True, pat="token")
    )
    await db.commit()
    return int(supplier["id"])


async def test_edp_search_returns_drafts_and_existing_items(buyer, festo) -> None:
    existing = await buyer.post(
        f"{ITEMS}/",
        json={"order_code_1": "19 210", "article_name": "Old", "manufacturer_id": festo},
    )

    hits = (await buyer.get(f"{EDP}/search", params={"q": "DSNU"})).json()["hits"]

    assert [h["part"]["part_id"] for h in hits] == [1, 2]
    draft = hits[0]["draft"]
    assert draft["manufacturer_id"] == festo
    assert draft["article_name"] == "Zylinder 19210"
    assert draft["product_family_id"] is not None
    assert hits[0]["existing_item"]["id"] == existing.json()["id"]
    assert hits[1]["existing_item"] is None


async def test_edp_create_with_a_part_links_it_and_requests_the_picture(
    buyer, festo, published_events: list[object]
) -> None:
    created = await buyer.post(
        f"{ITEMS}/",
        json={
            "order_code_1": "19211",
            "article_name": "Zylinder",
            "manufacturer_id": festo,
            "edp_part_id": 2,
        },
    )

    assert created.status_code == 201, created.text
    assert created.json()["edp_part_id"] == 2
    assert created.json()["edp_synced_at"] is not None
    assert any(isinstance(e, BoughtItemEdpPictureRequested) for e in published_events)


async def test_edp_lookup_compares_and_apply_writes_chosen_fields(buyer, festo) -> None:
    item = (
        await buyer.post(
            f"{ITEMS}/",
            json={"order_code_1": "19210", "article_name": "Mine", "manufacturer_id": festo},
        )
    ).json()

    lookup = (await buyer.get(f"{EDP}/items/{item['id']}/lookup")).json()

    assert lookup["part"]["part_id"] == 1
    fields = {f["field"]: f for f in lookup["fields"]}
    assert fields["article_name"]["differs"] is True
    assert fields["article_name"]["applicable"] is True
    assert fields["order_code_1"]["differs"] is False

    applied = await buyer.post(
        f"{EDP}/items/{item['id']}/apply",
        json={"part_id": 1, "fields": ["article_name", "order_code_2", "product_family_id"]},
    )

    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["article_name"] == "Zylinder 19210"
    assert body["order_code_2"] == "DSNU-19210"
    assert body["product_family"]["name"] == "Cylinders"
    assert body["edp_part_id"] == 1
    assert body["weblink"] is None


async def _type_number_first(client, festo: int) -> None:
    response = await client.put(
        f"{API_WEB}/suppliers/{festo}",
        json={
            "expected_edit_version": await row_version(client, f"{API_WEB}/suppliers/{festo}"),
            "name": "Festo SE",
            "edp_code": "FES",
            "edp_type_number_first": True,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["edp_type_number_first"] is True


async def test_edp_search_puts_the_type_number_first_for_such_a_manufacturer(buyer, festo) -> None:
    await _type_number_first(buyer, festo)
    existing = await buyer.post(
        f"{ITEMS}/",
        json={"order_code_1": "DSNU-19210", "article_name": "Old", "manufacturer_id": festo},
    )

    hits = (await buyer.get(f"{EDP}/search", params={"q": "DSNU"})).json()["hits"]

    draft = hits[0]["draft"]
    assert (draft["order_code_1"], draft["order_code_2"]) == ("DSNU-19210", "19210")
    assert hits[0]["existing_item"]["id"] == existing.json()["id"]


async def test_edp_lookup_keeps_the_type_number_first_item_unchanged(buyer, festo) -> None:
    await _type_number_first(buyer, festo)
    item = (
        await buyer.post(
            f"{ITEMS}/",
            json={
                "order_code_1": "DSNU-19210",
                "order_code_2": "19210",
                "article_name": "Mine",
                "manufacturer_id": festo,
                "edp_part_id": 1,
            },
        )
    ).json()

    lookup = (await buyer.get(f"{EDP}/items/{item['id']}/lookup")).json()

    fields = {f["field"]: f for f in lookup["fields"]}
    assert fields["order_code_1"]["differs"] is False
    assert fields["order_code_2"]["differs"] is False


async def test_edp_lookup_narrows_to_the_manufacturer_and_lists_candidates(buyer, festo) -> None:
    item = (
        await buyer.post(
            f"{ITEMS}/",
            json={"order_code_1": "19211", "article_name": "Mine", "manufacturer_id": festo},
        )
    ).json()

    lookup = (await buyer.get(f"{EDP}/items/{item['id']}/lookup")).json()

    assert lookup["part"]["part_id"] == 2
    assert lookup["candidates"] == []


async def test_edp_lookup_lists_candidates_without_a_manufacturer_code(buyer, festo) -> None:
    other = (await buyer.post(f"{API_WEB}/suppliers/", json={"name": "Nobody"})).json()
    item = (
        await buyer.post(
            f"{ITEMS}/",
            json={"order_code_1": "19211", "article_name": "Mine", "manufacturer_id": other["id"]},
        )
    ).json()

    lookup = (await buyer.get(f"{EDP}/items/{item['id']}/lookup")).json()

    assert [c["part_id"] for c in lookup["candidates"]] == [2, 3]
    picked = (await buyer.get(f"{EDP}/items/{item['id']}/lookup", params={"part_id": 3})).json()
    assert picked["part"]["part_id"] == 3


async def test_edp_apply_without_fields_only_links(buyer, festo) -> None:
    item = (
        await buyer.post(
            f"{ITEMS}/",
            json={"order_code_1": "19210", "article_name": "Mine", "manufacturer_id": festo},
        )
    ).json()

    body = (await buyer.post(f"{EDP}/items/{item['id']}/apply", json={"part_id": 1})).json()

    assert (body["article_name"], body["edp_part_id"]) == ("Mine", 1)


async def test_edp_search_needs_the_portal_switched_on(buyer, festo, db) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_edp(AdminEdpSettings(id=1))
    await db.commit()

    response = await buyer.get(f"{EDP}/search", params={"q": "DSNU"})

    assert response.json()["code"] == "EdpNotConfiguredError"


async def test_edp_part_picture_is_served_from_glados(buyer, festo, portal, monkeypatch) -> None:
    async def fetch_picture(url: str) -> bytes | None:
        return b"\x89PNG-bytes"

    portal.fetch_picture = fetch_picture
    monkeypatch.setitem(PARTS, 1, replace(PARTS[1], picture_url="https://blob.example.test/p.png"))

    response = await buyer.get(f"{EDP}/parts/1/picture")
    missing = await buyer.get(f"{EDP}/parts/2/picture")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == b"\x89PNG-bytes"
    assert missing.status_code == 404


async def test_edp_search_and_picture_need_the_data_portal_permission(auth_client, festo) -> None:
    """The bought item write permission alone opens neither lookup."""
    writer = await auth_client(
        username="writer",
        email="writer@example.com",
        permissions=[Permission.WRITE_BOUGHT_ITEMS],
    )

    search = await writer.get(f"{EDP}/search", params={"q": "DSNU"})
    picture = await writer.get(f"{EDP}/parts/1/picture")

    assert [search.status_code, picture.status_code] == [403, 403]


async def test_edp_search_needs_no_bought_item_write_permission(auth_client, festo) -> None:
    """A user who may only look parts up searches, but cannot create the item."""
    reader = await auth_client(
        username="reader",
        email="reader@example.com",
        permissions=[Permission.USE_DATA_PORTAL],
    )

    search = await reader.get(f"{EDP}/search", params={"q": "DSNU"})
    created = await reader.post(
        f"{ITEMS}/",
        json={"order_code_1": "19211", "article_name": "Zylinder", "manufacturer_id": festo},
    )

    assert search.status_code == 200, search.text
    assert created.status_code == 403
