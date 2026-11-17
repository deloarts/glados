"""
The bought-item batch create with the EPLAN Data Portal lookup, against a
fake portal swapped in through app.dependency_overrides: the portal fills
and wins, the manufacturer comes from the supplier's Data Portal code, the
default article groups apply, unknown and ambiguous numbers are reported,
a pinned candidate and a file-only row resolve, an existing item is linked
instead of imported, and the lookup refuses to run while the portal is off.
"""

from dataclasses import dataclass
from dataclasses import field
from typing import Any

import pytest

from src.bootstrap.adapters.outbound.persistence.admin_settings_seed import _data_import_defaults
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

IMPORT = f"{API_WEB}/bought-items-import"
ITEMS = f"{API_WEB}/bought-items"


def _part(part_id: int, order: str, code: str = "SIE", name: str = "Siemens") -> EdpPart:
    return EdpPart(
        part_id=part_id,
        part_number=f"{code}.{order}",
        order_number=order,
        type_number=f"TYPE-{order}",
        designation={"de_DE": f"Schuetz {order}", "en_US": f"Contactor {order}"},
        ean="4011209780774" if part_id == 1 else None,
        manufacturer_code=code,
        manufacturer_name=name,
        product_groups=("Electrical engineering", "Contactors"),
        support_url=f"https://support.example.test/{order}",
        picture_url="https://blob.example.test/p.png",
    )


PARTS = {
    1: _part(1, "3RT2015-1BB41"),
    2: _part(2, "DUP-1"),
    3: _part(3, "DUP-1b"),
    4: _part(4, "XYZ-9", code="UNK", name="Unknown maker"),
    5: _part(5, "OC-1"),
}
NUMBERS = {
    "3RT2015-1BB41": (1,),
    "SIE.3RT2015-1BB41": (1,),
    "DUP-1": (2, 3),
    "XYZ-9": (4,),
    "OC-1": (5,),
}


@dataclass
class _FakePortal:
    connections: list[EdpConnection] = field(default_factory=list)

    def factory(self, connection: EdpConnection) -> "_FakePortal":
        self.connections.append(connection)
        return self

    async def check_numbers(self, numbers: list[str]) -> list[EdpNumberMatch]:
        return [EdpNumberMatch(search=n, part_ids=NUMBERS.get(n, ())) for n in numbers]

    async def get_parts(self, part_ids: list[int]) -> list[EdpPart]:
        return [PARTS[i] for i in part_ids if i in PARTS]


@pytest.fixture
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
            Permission.WRITE_SUPPLIERS,
            Permission.WRITE_ARTICLE_GROUPS,
        ],
    )


@pytest.fixture
async def seeded(buyer, db) -> dict[str, int]:
    siemens = (
        await buyer.post(f"{API_WEB}/suppliers/", json={"name": "Siemens AG", "edp_code": "SIE"})
    ).json()
    family = (await buyer.post(f"{API_WEB}/product-families/", json={"name": "contactors"})).json()
    group = (
        await buyer.post(f"{API_WEB}/article-groups/", json={"name": {"enGB": "Electrics"}})
    ).json()
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_data_import(_data_import_defaults())
    await repo.save_edp(
        AdminEdpSettings(id=1, enabled=True, pat="token", default_article_group_ids=[group["id"]])
    )
    await db.commit()
    return {"supplier": siemens["id"], "family": family["id"], "group": group["id"]}


async def _validate(client: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    response = await client.post(f"{IMPORT}/validate", json={"rows": rows, "lookup": True})
    assert response.status_code == 200, response.text
    return list(response.json()["results"])


async def test_import_lookup_fills_the_row_from_the_portal(buyer, seeded, portal) -> None:
    [result] = await _validate(buyer, [{"row_index": 0, "order_code_1": "3RT2015-1BB41"}])

    assert result["row_status"] == "ready", result
    assert result["resolved_manufacturer_id"] == seeded["supplier"]
    assert result["resolved_product_family_id"] == seeded["family"]
    assert result["resolved_article_group_ids"] == [seeded["group"]]
    assert result["edp_part"]["part_id"] == 1
    assert result["edp_part"]["designation"] == "Schuetz 3RT2015-1BB41"
    assert portal.connections[0].pat == "token"


async def test_import_lookup_lets_the_portal_win_and_reports_the_file(
    buyer, seeded, portal
) -> None:
    [result] = await _validate(
        buyer,
        [
            {
                "row_index": 0,
                "edp_part_number": "SIE.3RT2015-1BB41",
                "order_code_1": "something else",
                "article_name": "My own name",
                "mass": 250,
            }
        ],
    )

    assert result["row_status"] == "ready"
    differences = {d["field"]: d for d in result["portal_differences"]}
    assert differences["article_name"]["portal_value"] == "Schuetz 3RT2015-1BB41"
    assert differences["order_code_1"]["file_value"] == "something else"


async def test_import_lookup_reports_unknown_ambiguous_and_unmapped(buyer, seeded, portal) -> None:
    results = await _validate(
        buyer,
        [
            {"row_index": 0, "order_code_1": "NOPE"},
            {"row_index": 1, "order_code_1": "DUP-1"},
            {"row_index": 2, "order_code_1": "XYZ-9"},
        ],
    )

    assert [r["row_status"] for r in results] == ["not_found", "ambiguous", "invalid"]
    assert [c["part_id"] for c in results[1]["candidates"]] == [2, 3]
    assert "UNK" in results[2]["errors"][0]


async def test_import_lookup_resolves_a_pinned_candidate_and_a_file_only_row(
    buyer, seeded, portal
) -> None:
    results = await _validate(
        buyer,
        [
            {"row_index": 0, "order_code_1": "DUP-1", "edp_part_id": 3},
            {
                "row_index": 1,
                "order_code_1": "NOPE",
                "article_name": "Special part",
                "manufacturer_name": "siemens ag",
                "skip_lookup": True,
            },
        ],
    )

    assert [r["row_status"] for r in results] == ["ready", "ready"]
    assert results[0]["edp_part"]["part_id"] == 3
    assert results[1]["edp_part"] is None


async def test_import_lookup_commit_creates_and_links(
    buyer, seeded, portal, published_events: list[object]
) -> None:
    existing = await buyer.post(
        f"{ITEMS}/",
        json={"order_code_1": "OC 1", "article_name": "Old", "manufacturer_id": seeded["supplier"]},
    )
    assert existing.status_code == 201, existing.text

    response = await buyer.post(
        f"{IMPORT}/commit",
        json={
            "lookup": True,
            "rows": [
                {"row_index": 0, "order_code_1": "3RT2015-1BB41"},
                {"row_index": 1, "order_code_1": "OC-1"},
                {"row_index": 2, "order_code_1": "NOPE"},
            ],
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created_row_indexes"] == [0]
    assert body["handled_row_indexes"] == [0, 1]
    assert body["linked_item_ids"] == [existing.json()["id"]]
    created = (await buyer.get(f"{ITEMS}/{body['created_item_ids'][0]}")).json()
    assert created["edp_part_id"] == 1
    assert created["article_name"] == "Schuetz 3RT2015-1BB41"
    assert created["order_code_2"] == "TYPE-3RT2015-1BB41"
    assert created["ean"] == "4011209780774"
    assert created["weblink"] == "https://support.example.test/3RT2015-1BB41"
    linked = (await buyer.get(f"{ITEMS}/{existing.json()['id']}")).json()
    assert linked["edp_part_id"] == 5
    assert linked["article_name"] == "Old"
    pictures = [e for e in published_events if isinstance(e, BoughtItemEdpPictureRequested)]
    assert len(pictures) == 2


async def test_import_lookup_refuses_while_the_portal_is_off(buyer, seeded, db, portal) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_edp(AdminEdpSettings(id=1, enabled=False, pat="token"))
    await db.commit()

    response = await buyer.post(
        f"{IMPORT}/validate", json={"rows": [{"row_index": 0, "order_code_1": "X"}], "lookup": True}
    )

    assert response.status_code == 400
    assert response.json()["code"] == "EdpNotConfiguredError"
