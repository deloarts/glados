"""
Over HTTP: a new demand needs an item new work may name and an active
project, a new lot needs an active project, and a new revision gives its
predecessor the status the admin setting fixes for the web.
"""

from datetime import UTC
from datetime import datetime
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
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus

WEB = "/api/v1/web"


def _made_item_settings(predecessor_status_web: str = "ask") -> AdminMadeItemSettings:
    return AdminMadeItemSettings(
        id=1,
        item_number_format="FAB-{yy}-{seq:05d}",
        lot_number_format="LOT-{yy}-{seq:05d}",
        part_number_auto=True,
        part_number_editable=False,
        revision_start="0",
        revision_separator=":",
        revision_skip_ambiguous_letters=False,
        revision_only_newest_editable=True,
        revision_predecessor_status_web=predecessor_status_web,
        revision_predecessor_status_pdm="replaced",
        revision_field_policy=default_policy(),
        web_creation_allowed=True,
        pdm_part_number_pattern="",
    )


@pytest.fixture(autouse=True)
async def _seed_settings(db: AsyncSession) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_made_items(_made_item_settings())
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
    await repo.save_production(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PON-{yy}-{seq:05d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=0,
            response_time_days=1,
            require_qa=False,
        )
    )
    await db.commit()


@pytest.fixture
async def web(auth_client) -> httpx.AsyncClient:
    return await auth_client(
        permissions=[
            Permission.WRITE_SUPPLIERS,
            Permission.WRITE_BOUGHT_ITEMS,
            Permission.DELETE_BOUGHT_ITEMS,
            Permission.WRITE_MADE_ITEMS,
            Permission.WRITE_DEMAND_ITEMS,
            Permission.WRITE_LOTS,
        ]
    )


async def _project(
    db: AsyncSession, number: str, status: ProjectStatus = ProjectStatus.ACTIVE
) -> Project:
    saved = await SqlAlchemyProjectRepository(db).save(
        Project(
            id=0,
            created=datetime(2026, 10, 1, tzinfo=UTC),
            creator_id=1,
            project_number=number,
            status=status,
        )
    )
    await db.commit()
    return saved


async def _created(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 201, response.text
    return dict(response.json())


async def _bought_item(web: httpx.AsyncClient) -> dict[str, Any]:
    supplier = await _created(
        await web.post(f"{WEB}/suppliers/", json={"name": "Acme", "level": "B"})
    )
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


async def _demand(web: httpx.AsyncClient, item_id: int, project_id: int) -> httpx.Response:
    return await web.post(
        f"{WEB}/bought-items-demands/",
        json={"item_id": item_id, "project_id": project_id, "quantity": 2.0, "unit": "pcs"},
    )


async def test_an_archived_bought_item_takes_no_new_demand(web, db: AsyncSession) -> None:
    project = await _project(db, "P-1")
    item = await _bought_item(web)
    archived = await web.post(f"{WEB}/bought-items/{item['id']}/archive")
    assert archived.status_code == 200, archived.text

    resp = await _demand(web, item["id"], project.id)

    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "BoughtItemInactiveError"
    assert "is archived" in resp.json()["detail"]


async def test_a_project_on_hold_takes_no_new_demand(web, db: AsyncSession) -> None:
    project = await _project(db, "P-2", status=ProjectStatus.ON_HOLD)
    item = await _bought_item(web)

    resp = await _demand(web, item["id"], project.id)

    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "ProjectInactiveError"


async def test_a_project_on_hold_takes_no_new_lot(web, db: AsyncSession) -> None:
    project = await _project(db, "P-3", status=ProjectStatus.ON_HOLD)
    made_item = await _created(
        await web.post(f"{WEB}/made-items/", json={"revision": "A", "article_name": "Bracket"})
    )

    resp = await web.post(
        f"{WEB}/production-lots/",
        json={"made_item_id": made_item["id"], "project_id": project.id, "quantity": 5.0},
    )

    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "ProjectInactiveError"


async def test_a_fixed_web_setting_decides_the_predecessor_status(web, db: AsyncSession) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_made_items(_made_item_settings("inactive"))
    await db.commit()
    made_item = await _created(
        await web.post(f"{WEB}/made-items/", json={"revision": "A", "article_name": "Bracket"})
    )

    revised = await web.post(
        f"{WEB}/made-items/{made_item['id']}/revisions",
        json={"predecessor_status": "replaced", "item": {"article_name": "Bracket"}},
    )

    assert revised.status_code == 201, revised.text
    predecessor = (await web.get(f"{WEB}/made-items/{made_item['id']}")).json()
    assert predecessor["status"] == "inactive"
    assert predecessor["successor_item_id"] is None
