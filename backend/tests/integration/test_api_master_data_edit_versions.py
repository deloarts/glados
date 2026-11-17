"""
Edit versions of master data over HTTP. Every change of a supplier, item,
product or device moves its edit version, whoever writes it: a web form, the
`pat` API or a system write such as a PDM ingest. A web edit sent with an
older version answers 409 and changes nothing, one sent without it is
refused with 422, and a `pat` edit may leave it out. A save that changes no
field, or a write of sync bookkeeping alone, leaves the version where it is.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
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
SUPPLIER = {"name": "Acme", "level": "B"}


@pytest.fixture(autouse=True)
async def _seed_order_settings(db: AsyncSession) -> None:
    """Numbers the bought items the tests create."""
    await SqlAlchemyAdminSettingsRepository(db).save_orders(
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
async def web(auth_client) -> httpx.AsyncClient:
    return await auth_client(
        permissions=[
            Permission.WRITE_SUPPLIERS,
            Permission.DELETE_SUPPLIERS,
            Permission.WRITE_BOUGHT_ITEMS,
            Permission.WRITE_PROJECTS,
            Permission.MANAGE_PROJECTS,
        ]
    )


@pytest.fixture
def mint_pat(db: AsyncSession, create_user) -> Callable[[], Awaitable[str]]:
    async def _mint() -> str:
        owner: User = await create_user(
            username="pat-owner",
            email="pat-owner@example.com",
            permissions=[Permission.WRITE_PAT, Permission.WRITE_BOUGHT_ITEMS],
        )
        result = await CreatePat(
            SqlAlchemyPatRepository(db),
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
        ).execute(
            actor=owner,
            cmd=CreatePatCommand(name="add-in", permissions=[Permission.WRITE_BOUGHT_ITEMS]),
        )
        return result.token

    return _mint


async def _created(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 201, response.text
    return dict(response.json())


async def _bought_item(web: httpx.AsyncClient) -> dict[str, Any]:
    supplier = await _created(await web.post(f"{WEB}/suppliers/", json=SUPPLIER))
    return await _created(
        await web.post(
            f"{WEB}/bought-items/",
            json={
                "order_code_1": "OC-1",
                "article_name": "Bolt",
                "manufacturer_id": supplier["id"],
            },
        )
    )


def _bought_body(item: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {
        "order_code_1": item["order_code_1"],
        "article_name": item["article_name"],
        "manufacturer_id": item["manufacturer_id"],
        "part_number": item["part_number"],
        "status": item["status"],
        **changes,
    }


# ── The web form ─────────────────────────────────────────────────────────


async def test_an_edit_with_the_version_read_goes_through_and_moves_it(web) -> None:
    supplier = await _created(await web.post(f"{WEB}/suppliers/", json=SUPPLIER))
    assert supplier["edit_version"] == 0

    edited = await web.put(
        f"{WEB}/suppliers/{supplier['id']}",
        json={**SUPPLIER, "name": "Acme GmbH", "expected_edit_version": 0},
    )

    assert edited.status_code == 200, edited.text
    assert edited.json()["edit_version"] == 1
    assert await row_version(web, f"/suppliers/{supplier['id']}") == 1


async def test_an_edit_with_an_older_version_is_refused_and_changes_nothing(web) -> None:
    supplier = await _created(await web.post(f"{WEB}/suppliers/", json=SUPPLIER))
    url = f"{WEB}/suppliers/{supplier['id']}"
    first = await web.put(url, json={**SUPPLIER, "name": "First", "expected_edit_version": 0})
    assert first.status_code == 200, first.text

    second = await web.put(url, json={**SUPPLIER, "name": "Second", "expected_edit_version": 0})

    assert second.status_code == 409, second.text
    assert second.json()["code"] == "ConcurrentModificationError"
    assert (await web.get(url)).json()["name"] == "First"


async def test_an_edit_without_a_version_is_refused(web) -> None:
    supplier = await _created(await web.post(f"{WEB}/suppliers/", json=SUPPLIER))

    response = await web.put(f"{WEB}/suppliers/{supplier['id']}", json=SUPPLIER)

    assert response.status_code == 422, response.text
    assert any(e["loc"][-1] == "expected_edit_version" for e in response.json()["detail"])


async def test_a_save_that_changes_nothing_leaves_the_version_alone(web) -> None:
    supplier = await _created(await web.post(f"{WEB}/suppliers/", json=SUPPLIER))

    saved = await web.put(
        f"{WEB}/suppliers/{supplier['id']}", json={**SUPPLIER, "expected_edit_version": 0}
    )

    assert saved.status_code == 200, saved.text
    assert saved.json()["edit_version"] == 0


async def test_archiving_moves_the_version_so_an_open_form_is_refused(web) -> None:
    supplier = await _created(await web.post(f"{WEB}/suppliers/", json=SUPPLIER))
    url = f"{WEB}/suppliers/{supplier['id']}"

    archived = await web.post(f"{url}/archive")
    stale = await web.put(url, json={**SUPPLIER, "name": "Late", "expected_edit_version": 0})

    assert archived.json()["edit_version"] == 1
    assert stale.status_code == 409, stale.text


# ── Other writers ────────────────────────────────────────────────────────


async def test_a_pat_edit_may_leave_the_version_out_and_still_moves_it(
    web, client: httpx.AsyncClient, mint_pat
) -> None:
    item = await _bought_item(web)
    headers = {"X-Api-Key": await mint_pat()}

    edited = await client.put(
        f"{PAT}/bought-items/{item['id']}",
        json=_bought_body(item, article_name="Hex bolt"),
        headers=headers,
    )
    stale = await web.put(
        f"{WEB}/bought-items/{item['id']}",
        json=_bought_body(item, article_name="Bolt M8", expected_edit_version=0),
    )

    assert edited.status_code == 200, edited.text
    assert edited.json()["edit_version"] == 1
    assert stale.status_code == 409, stale.text


async def test_a_pat_edit_with_an_older_version_is_refused(
    web, client: httpx.AsyncClient, mint_pat
) -> None:
    item = await _bought_item(web)
    first = await web.put(
        f"{WEB}/bought-items/{item['id']}",
        json=_bought_body(item, article_name="Hex bolt", expected_edit_version=0),
    )
    assert first.status_code == 200, first.text

    stale = await client.put(
        f"{PAT}/bought-items/{item['id']}",
        json=_bought_body(item, article_name="Bolt M8", expected_edit_version=0),
        headers={"X-Api-Key": await mint_pat()},
    )

    assert stale.status_code == 409, stale.text


async def test_a_system_write_moves_the_version_unless_it_only_stamps_bookkeeping(
    web, db: AsyncSession
) -> None:
    item = await _bought_item(web)
    url = f"/bought-items/{item['id']}"

    row = await db.get(BoughtItemOrmModel, item["id"])
    assert row is not None
    row.pdm_synced_at = datetime(2026, 11, 1, tzinfo=UTC)
    row.edp_synced_at = datetime(2026, 11, 1, tzinfo=UTC)
    await db.commit()
    assert await row_version(web, url) == 0

    row.article_name = "Bolt from PDM"
    await db.commit()
    assert await row_version(web, url) == 1


# ── Projects ─────────────────────────────────────────────────────────────


async def test_a_project_delete_needs_the_version_read(web) -> None:
    project = await _created(await web.post(f"{WEB}/projects/", json={"project_number": "J-100"}))
    url = f"{WEB}/projects/{project['id']}"
    edited = await web.put(
        url, json={"project_number": "J-100", "description": "x", "expected_edit_version": 0}
    )
    assert edited.status_code == 200, edited.text

    without = await web.delete(url)
    stale = await web.delete(url, params={"expected_edit_version": 0})
    deleted = await web.delete(url, params={"expected_edit_version": 1})

    assert (without.status_code, stale.status_code, deleted.status_code) == (422, 409, 200)
