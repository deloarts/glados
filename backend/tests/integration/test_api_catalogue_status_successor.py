"""
Status and successor of catalogue items over HTTP, on the web routes of the
three catalogues and on the `pat` bought item routes the SolidWorks add-in
can call. The request shapes are unchanged; only combinations that do not fit
are refused, and a successor that does not exist is a 404 instead of a
database error.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._edit_versions import row_version

WEB = "/api/v1/web"
PAT = "/api/v1/pat"
NOT_FOUND_ID = 424242


@pytest.fixture(autouse=True)
async def _seed_numbering_settings(db: AsyncSession) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_made_items(
        AdminMadeItemSettings(
            id=1,
            item_number_format="FAB-{yy}-{seq:05d}",
            lot_number_format="LOT-{yy}-{seq:05d}",
            part_number_auto=True,
            part_number_editable=False,
            revision_start="0",
            revision_separator=":",
            revision_skip_ambiguous_letters=False,
            revision_only_newest_editable=True,
            revision_predecessor_status_web="ask",
            revision_predecessor_status_pdm="replaced",
            revision_field_policy=default_policy(),
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
    )
    await db.commit()
    await repo.save_orders(
        AdminOrderSettings(
            id=1,
            order_number_format="ORD-{yy}-{seq:05d}",
            part_number_format="PUR-{yy}-{seq:05d}",
            part_number_auto=True,
            part_number_editable=False,
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
    )
    await db.commit()


@pytest.fixture
async def pat_owner(create_user) -> User:
    return await create_user(
        username="pat-owner",
        email="pat-owner@example.com",
        permissions=[Permission.WRITE_PAT, Permission.WRITE_BOUGHT_ITEMS],
    )


@pytest.fixture
def mint_pat(db: AsyncSession, pat_owner: User) -> Callable[[list[str]], Awaitable[str]]:
    async def _mint(permissions: list[str]) -> str:
        result = await CreatePat(
            SqlAlchemyPatRepository(db),
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
        ).execute(actor=pat_owner, cmd=CreatePatCommand(name="status-pat", permissions=permissions))
        return result.token

    return _mint


@pytest.fixture
async def web(auth_client) -> httpx.AsyncClient:
    return await auth_client(
        permissions=[
            Permission.WRITE_SUPPLIERS,
            Permission.WRITE_BOUGHT_ITEMS,
            Permission.WRITE_MADE_ITEMS,
            Permission.DELETE_MADE_ITEMS,
            Permission.WRITE_SOURCE_ITEMS,
            Permission.WRITE_SOURCE_ITEM_TYPES,
        ]
    )


async def _created(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 201, response.text
    return dict(response.json())


async def _bought_items(web: httpx.AsyncClient, count: int) -> list[dict[str, Any]]:
    supplier = await _created(
        await web.post(f"{WEB}/suppliers/", json={"name": "Acme", "level": "B"})
    )
    return [
        await _created(
            await web.post(
                f"{WEB}/bought-items/",
                json={
                    "order_code_1": f"OC-{n}",
                    "article_name": f"Bolt {n}",
                    "manufacturer_id": supplier["id"],
                },
            )
        )
        for n in range(count)
    ]


def _bought_body(item: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {
        "order_code_1": item["order_code_1"],
        "article_name": item["article_name"],
        "manufacturer_id": item["manufacturer_id"],
        "part_number": item["part_number"],
        "status": item["status"],
        "successor_item_id": item["successor_item_id"],
        **changes,
    }


# ── Bought items, web and pat ────────────────────────────────────────────


async def test_a_successor_that_does_not_exist_is_a_404_not_a_500(web) -> None:
    (item,) = await _bought_items(web, 1)

    resp = await web.put(
        f"{WEB}/bought-items/{item['id']}",
        json={
            **_bought_body(item, status="replaced", successor_item_id=NOT_FOUND_ID),
            "expected_edit_version": await row_version(web, f"{WEB}/bought-items/{item['id']}"),
        },
    )

    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "CatalogueSuccessorNotFoundError"


async def test_the_pat_put_keeps_its_shape_and_refuses_only_what_does_not_fit(
    web, client: httpx.AsyncClient, mint_pat
) -> None:
    item, successor = await _bought_items(web, 2)
    headers = {"X-Api-Key": await mint_pat([Permission.WRITE_BOUGHT_ITEMS])}
    url = f"{PAT}/bought-items/{item['id']}"

    without = await client.put(url, json=_bought_body(item, status="replaced"), headers=headers)
    assert without.status_code == 409, without.text
    assert without.json()["code"] == "CatalogueStatusChangeError"

    replaced = await client.put(
        url,
        json=_bought_body(item, status="replaced", successor_item_id=successor["id"]),
        headers=headers,
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["successor_item_id"] == successor["id"]

    reactivated = await client.put(
        url,
        json=_bought_body(item, status="active", successor_item_id=successor["id"]),
        headers=headers,
    )
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["status"] == "active"
    assert reactivated.json()["successor_item_id"] is None


async def test_a_bought_item_cannot_be_created_replaced_over_pat(
    web, client: httpx.AsyncClient, mint_pat
) -> None:
    supplier = await _created(
        await web.post(f"{WEB}/suppliers/", json={"name": "Acme", "level": "B"})
    )
    headers = {"X-Api-Key": await mint_pat([Permission.WRITE_BOUGHT_ITEMS])}

    resp = await client.post(
        f"{PAT}/bought-items/",
        json={
            "order_code_1": "OC-NEW",
            "article_name": "Bolt",
            "manufacturer_id": supplier["id"],
            "status": "replaced",
        },
        headers=headers,
    )

    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "CatalogueStatusChangeError"


# ── Made items ───────────────────────────────────────────────────────────


async def _made_item(web: httpx.AsyncClient, name: str) -> dict[str, Any]:
    return await _created(
        await web.post(f"{WEB}/made-items/", json={"revision": "A", "article_name": name})
    )


def _made_body(item: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {
        "article_name": item["article_name"],
        "part_number": item["part_number"],
        "status": item["status"],
        "successor_item_id": item["successor_item_id"],
        **changes,
    }


async def test_a_made_item_cannot_succeed_itself(web) -> None:
    item = await _made_item(web, "Bracket")

    resp = await web.put(
        f"{WEB}/made-items/{item['id']}",
        json={
            **_made_body(item, status="replaced", successor_item_id=item["id"]),
            "expected_edit_version": await row_version(web, f"{WEB}/made-items/{item['id']}"),
        },
    )

    assert resp.status_code == 409, resp.text
    assert "its own successor" in resp.json()["detail"]


async def test_an_archived_made_item_cannot_be_the_successor(web) -> None:
    item = await _made_item(web, "Bracket")
    successor = await _made_item(web, "Bracket Mk2")
    archived = await web.post(f"{WEB}/made-items/{successor['id']}/archive")
    assert archived.status_code == 200, archived.text

    resp = await web.put(
        f"{WEB}/made-items/{item['id']}",
        json={
            **_made_body(item, status="replaced", successor_item_id=successor["id"]),
            "expected_edit_version": await row_version(web, f"{WEB}/made-items/{item['id']}"),
        },
    )

    assert resp.status_code == 409, resp.text
    assert "archived" in resp.json()["detail"]


# ── Source items ─────────────────────────────────────────────────────────


async def test_a_source_item_successor_that_does_not_exist_is_a_404(web) -> None:
    item_type = await _created(
        await web.post(f"{WEB}/source-item-types/", json={"name": {"enGB": "Round bar"}})
    )
    item = await _created(
        await web.post(
            f"{WEB}/source-items/",
            json={"type_id": item_type["id"], "dimension": "40mm", "material": "1.0037"},
        )
    )

    resp = await web.put(
        f"{WEB}/source-items/{item['id']}",
        json={
            "expected_edit_version": await row_version(web, f"{WEB}/source-items/{item['id']}"),
            "type_id": item_type["id"],
            "dimension": "40mm",
            "material": "1.0037",
            "status": "replaced",
            "successor_item_id": NOT_FOUND_ID,
        },
    )

    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "CatalogueSuccessorNotFoundError"


# ── Status is required on every update ───────────────────────────────────


async def _inactive(web: httpx.AsyncClient, url: str, body: dict[str, Any]) -> None:
    version = await row_version(web, url)
    resp = await web.put(url, json={**body, "status": "inactive", "expected_edit_version": version})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "inactive"


def _missing_status(resp: httpx.Response) -> bool:
    return resp.status_code == 422 and any(
        error["loc"][-1] == "status" and error["type"] == "missing"
        for error in resp.json()["detail"]
    )


async def test_an_update_without_status_is_refused_and_keeps_the_status(
    web, client: httpx.AsyncClient, mint_pat
) -> None:
    (bought,) = await _bought_items(web, 1)
    made = await _made_item(web, "Bracket")
    item_type = await _created(
        await web.post(f"{WEB}/source-item-types/", json={"name": {"enGB": "Round bar"}})
    )
    source_body = {"type_id": item_type["id"], "dimension": "40mm", "material": "1.0037"}
    source = await _created(await web.post(f"{WEB}/source-items/", json=source_body))
    pat_headers = {"X-Api-Key": await mint_pat([Permission.WRITE_BOUGHT_ITEMS])}

    cases = [
        (f"{WEB}/bought-items/{bought['id']}", _bought_body(bought), {}),
        (f"{PAT}/bought-items/{bought['id']}", _bought_body(bought), pat_headers),
        (f"{WEB}/made-items/{made['id']}", _made_body(made), {}),
        (f"{WEB}/source-items/{source['id']}", source_body, {}),
    ]
    for url, body, headers in cases:
        await _inactive(web, url.replace(PAT, WEB), body)
        without = {key: value for key, value in body.items() if key != "status"}

        caller = client if headers else web
        resp = await caller.put(url, json=without, headers=headers)

        assert _missing_status(resp), resp.text
        reread = await web.get(url.replace(PAT, WEB))
        assert reread.json()["status"] == "inactive", url
