"""
The read-only EPLAN Data Portal routes of the pat surface, which the
SolidWorks add-in calls with a personal access token, against a fake
portal: the switched-on status, the exact match on an order code with its
manufacturer narrowing, the permission they share with the web's search,
and the picture pass-through.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import replace
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.external_data.adapters.inbound.api.deps.services import (
    get_eplan_data_portal_factory,
)
from src.modules.external_data.domain.entities.admin_settings.eplan_data_portal import (
    AdminEdpSettings,
)
from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpNumberMatch
from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpPart
from src.modules.external_data.ports.outbound.eplan_data_portal_port import EdpConnection
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.const import API_PAT
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.token_permission_rules import SOLIDWORKS_ADDIN_SCOPES
from src.modules.platform.domain.value_objects.permission import Permission

EDP = f"{API_PAT}/bought-items-edp"


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

    async def fetch_picture(self, url: str) -> bytes | None:
        return b"\x89PNG-bytes"


@pytest.fixture(autouse=True)
def portal() -> Any:
    fake = _FakePortal()
    app.dependency_overrides[get_eplan_data_portal_factory] = lambda: fake.factory
    yield fake
    app.dependency_overrides.pop(get_eplan_data_portal_factory, None)


@pytest.fixture
async def pat_owner(create_user) -> User:
    return await create_user(
        username="pat-owner",
        email="pat-owner@example.com",
        permissions=[
            Permission.WRITE_PAT,
            Permission.WRITE_SOURCE_ITEMS,
            Permission.WRITE_BOUGHT_ITEMS,
            Permission.USE_DATA_PORTAL,
        ],
    )


@pytest.fixture
def pat_headers(db: AsyncSession, pat_owner: User) -> Callable[[list[str]], Awaitable[dict]]:
    """The header of a real PAT minted through CreatePat with `permissions`."""

    async def _mint(permissions: list[str]) -> dict[str, str]:
        result = await CreatePat(
            SqlAlchemyPatRepository(db),
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
        ).execute(actor=pat_owner, cmd=CreatePatCommand(name="add-in", permissions=permissions))
        return {"X-Api-Key": result.token}

    return _mint


@pytest.fixture
async def festo(auth_client, db) -> int:
    """A supplier carrying the portal code FES, an item already describing
    part 2, and the portal switched on."""
    buyer = await auth_client(
        username="buyer",
        email="buyer@example.com",
        permissions=[Permission.WRITE_BOUGHT_ITEMS, Permission.WRITE_SUPPLIERS],
    )
    supplier = (
        await buyer.post(f"{API_WEB}/suppliers/", json={"name": "Festo SE", "edp_code": "FES"})
    ).json()
    await buyer.post(
        f"{API_WEB}/bought-items/",
        json={"order_code_1": "19211", "article_name": "Mine", "manufacturer_id": supplier["id"]},
    )
    await SqlAlchemyAdminSettingsRepository(db).save_edp(
        AdminEdpSettings(id=1, enabled=True, pat="token")
    )
    await db.commit()
    return int(supplier["id"])


async def test_status_follows_the_settings_for_any_token(
    client: httpx.AsyncClient, pat_headers, db
) -> None:
    headers = await pat_headers([])
    await SqlAlchemyAdminSettingsRepository(db).save_edp(AdminEdpSettings(id=1, enabled=True))
    await db.commit()
    without_token = (await client.get(f"{EDP}/status", headers=headers)).json()

    await SqlAlchemyAdminSettingsRepository(db).save_edp(
        AdminEdpSettings(id=1, enabled=True, pat="token")
    )
    await db.commit()
    switched_on = (await client.get(f"{EDP}/status", headers=headers)).json()

    assert without_token == {"enabled": False}
    assert switched_on == {"enabled": True}


async def test_status_needs_a_token(client: httpx.AsyncClient) -> None:
    assert (await client.get(f"{EDP}/status")).status_code == 401


async def test_match_returns_every_part_a_number_names(
    client: httpx.AsyncClient, pat_headers, festo
) -> None:
    headers = await pat_headers([Permission.USE_DATA_PORTAL])

    hits = (await client.get(f"{EDP}/match", params={"number": "19211"}, headers=headers)).json()[
        "hits"
    ]

    assert [h["part"]["part_id"] for h in hits] == [2, 3]
    assert hits[0]["draft"]["manufacturer_id"] == festo
    assert hits[0]["draft"]["order_code_1"] == "19211"
    assert hits[0]["existing_item"]["article_name"] == "Mine"
    assert hits[1]["draft"]["manufacturer_id"] is None


async def test_match_narrows_to_the_manufacturers_parts(
    client: httpx.AsyncClient, pat_headers, festo
) -> None:
    headers = await pat_headers([Permission.USE_DATA_PORTAL])

    response = await client.get(
        f"{EDP}/match", params={"number": "19211", "manufacturer_id": festo}, headers=headers
    )

    assert [h["part"]["part_id"] for h in response.json()["hits"]] == [2]


async def test_match_of_an_unknown_number_is_empty(
    client: httpx.AsyncClient, pat_headers, festo
) -> None:
    headers = await pat_headers([Permission.USE_DATA_PORTAL])

    response = await client.get(f"{EDP}/match", params={"number": "00000"}, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"hits": []}


async def test_lookups_need_the_data_portal_permission(
    client: httpx.AsyncClient, pat_headers, festo
) -> None:
    """The bought item write permission alone no longer opens the lookups."""
    headers = await pat_headers([Permission.WRITE_BOUGHT_ITEMS])

    match = await client.get(f"{EDP}/match", params={"number": "19211"}, headers=headers)
    search = await client.get(f"{EDP}/search", params={"q": "DSNU"}, headers=headers)
    picture = await client.get(f"{EDP}/parts/1/picture", headers=headers)

    assert [match.status_code, search.status_code, picture.status_code] == [403, 403, 403]


async def test_the_addin_token_preset_reaches_the_lookups(
    client: httpx.AsyncClient, pat_headers, festo
) -> None:
    headers = await pat_headers(list(SOLIDWORKS_ADDIN_SCOPES))

    response = await client.get(f"{EDP}/match", params={"number": "19211"}, headers=headers)

    assert response.status_code == 200, response.text
    assert [h["part"]["part_id"] for h in response.json()["hits"]] == [2, 3]


async def test_match_needs_the_portal_switched_on(
    client: httpx.AsyncClient, pat_headers, festo, db
) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_edp(AdminEdpSettings(id=1))
    await db.commit()
    headers = await pat_headers([Permission.USE_DATA_PORTAL])

    response = await client.get(f"{EDP}/match", params={"number": "19211"}, headers=headers)

    assert response.json()["code"] == "EdpNotConfiguredError"


async def test_search_and_picture_reach_the_portal(
    client: httpx.AsyncClient, pat_headers, festo, monkeypatch
) -> None:
    monkeypatch.setitem(PARTS, 1, replace(PARTS[1], picture_url="https://blob.example.test/p.png"))
    headers = await pat_headers([Permission.USE_DATA_PORTAL])

    search = await client.get(f"{EDP}/search", params={"q": "DSNU"}, headers=headers)
    picture = await client.get(f"{EDP}/parts/1/picture", headers=headers)

    assert [h["part"]["part_id"] for h in search.json()["hits"]] == [1, 2]
    assert picture.status_code == 200
    assert picture.headers["content-type"] == "image/png"
    assert picture.content == b"\x89PNG-bytes"
