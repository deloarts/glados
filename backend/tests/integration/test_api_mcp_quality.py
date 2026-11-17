"""
HTTP-level coverage of Quality's agent tools on the MCP surface: the
production KPIs, the report journal and the controlled documents of a
product. Documents are created through their web routes by the token's
owner, projects and products through the real repositories, and every tool
is called the way an agent client calls it.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.product_repository import (
    SqlAlchemyProductRepository,
)
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.entities.project import Project
from tests.integration._mcp_helpers import call_tool
from tests.integration._mcp_helpers import mint_agent_token
from tests.integration._mcp_helpers import save_agent_settings
from tests.integration.conftest import auth_headers

API_WEB = "/api/v1/web"


@pytest.fixture
async def agents_on(db: AsyncSession) -> None:
    await save_agent_settings(db)


@pytest.fixture
async def agent_owner(create_user: Callable[..., Awaitable[User]]) -> User:
    return await create_user(
        username="quality-planner",
        email="quality-planner@example.com",
        permissions=[
            Permission.WRITE_PAT,
            Permission.USE_MCP,
            Permission.WRITE_CHECKLISTS,
            Permission.WRITE_CALCULATIONS,
            Permission.WRITE_SEQUENCES,
        ],
    )


@pytest.fixture
def mint(db: AsyncSession, agent_owner: User) -> Callable[..., Awaitable[str]]:
    async def _mint(permissions: list[str], expires_in_days: int | None = 7) -> str:
        return await mint_agent_token(db, agent_owner, permissions, expires_in_days=expires_in_days)

    return _mint


async def _created(
    client: httpx.AsyncClient, user: User, path: str, body: dict[str, Any]
) -> dict[str, Any]:
    response = await client.post(f"{API_WEB}/{path}", json=body, headers=await auth_headers(user))
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def _calculation(**overrides: Any) -> dict[str, Any]:
    return {
        "tool": "drive_sizing",
        "title": "Vertical axis, 140 kg",
        "inputs": {"o": "vertical"},
        "results": {"torque": 12.5},
        "input_version": 1,
        "engine_version": 1,
    } | overrides


async def _product_with_project(db: AsyncSession, creator_id: int) -> tuple[int, int]:
    product = await SqlAlchemyProductRepository(db).save(
        Product(id=0, created=datetime.now(UTC), creator_id=creator_id, product_number="PR-MCP-Q")
    )
    project = await SqlAlchemyProjectRepository(db).save(
        Project(
            id=0,
            created=datetime.now(UTC),
            creator_id=creator_id,
            project_number="P-MCP-Q",
            product_id=product.id,
        )
    )
    await db.commit()
    return product.id, project.id


# ── production_kpis ───────────────────────────────────────────────────


@pytest.mark.usefixtures("agents_on")
async def test_production_kpis_answers_the_requested_views_of_a_period(
    client: httpx.AsyncClient, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP])

    result = await call_tool(
        client,
        token,
        "production_kpis",
        {"date_from": "2026-10-26", "date_to": "2026-11-01", "views": ["summary", "late_lots"]},
    )

    assert result["isError"] is False, result
    data = result["structuredContent"]
    assert data["date_from"] == "2026-10-26"
    assert "schedule_adherence" in data["summary"]
    assert data["late_lots"] == {"total": 0, "rows": []}
    assert "weekly" not in data


@pytest.mark.usefixtures("agents_on")
async def test_production_kpis_refuses_a_period_that_ends_before_it_starts(
    client: httpx.AsyncClient, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP])

    result = await call_tool(
        client, token, "production_kpis", {"date_from": "2026-11-02", "date_to": "2026-11-01"}
    )

    assert result["isError"] is True
    assert "date_to" in result["content"][0]["text"]


# ── report_journal ────────────────────────────────────────────────────


@pytest.mark.usefixtures("agents_on")
async def test_report_journal_lists_the_downloads_of_a_calculation_report(
    client: httpx.AsyncClient, agent_owner: User, mint: Callable[..., Awaitable[str]]
) -> None:
    calculation = await _created(client, agent_owner, "calculations", _calculation())
    await _created(
        client,
        agent_owner,
        "report-journal/downloads",
        {
            "document": "calculation_report",
            "root_public_id": calculation["public_id"],
            "facts": {"language": "enGB", "options": {}, "report_version": "0.1.0"},
            "byte_size": 1234,
            "sha256": "ab" * 32,
        },
    )
    token = await mint([Permission.USE_MCP])

    result = await call_tool(
        client,
        token,
        "report_journal",
        {"document": "calculation_report", "root_public_id": calculation["public_id"]},
    )

    assert result["isError"] is False, result
    data = result["structuredContent"]
    assert data["total"] == 1
    [entry] = data["items"]
    assert (entry["action"], entry["revision"], entry["byte_size"]) == (
        "download",
        calculation["revision"],
        1234,
    )
    assert entry["actor_full_name"] == "[hidden]"


@pytest.mark.usefixtures("agents_on")
async def test_report_journal_of_an_unknown_record_is_an_error_the_agent_reads(
    client: httpx.AsyncClient, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP])

    result = await call_tool(
        client,
        token,
        "report_journal",
        {
            "document": "checklist_report",
            "root_public_id": "00000000-0000-0000-0000-000000000000",
        },
    )

    assert result["isError"] is True


# ── controlled_documents ──────────────────────────────────────────────


@pytest.mark.usefixtures("agents_on")
async def test_controlled_documents_lists_every_kind_of_a_product_and_its_projects(
    client: httpx.AsyncClient,
    db: AsyncSession,
    agent_owner: User,
    mint: Callable[..., Awaitable[str]],
) -> None:
    product_id, project_id = await _product_with_project(db, agent_owner.id)
    checklist = await _created(
        client,
        agent_owner,
        "checklists",
        {
            "type": "hydraulics",
            "title": "Hydraulics checklist",
            "header": {"designation": "Press 12"},
            "answers": {},
            "remarks": {},
            "definition_version": 1,
            "item_count": 3,
            "product_id": product_id,
        },
    )
    calculation = await _created(
        client, agent_owner, "calculations", _calculation(project_id=project_id)
    )
    sequence = await _created(
        client, agent_owner, "sequences", {"product_id": product_id, "name": "Automatic"}
    )
    token = await mint([Permission.USE_MCP])

    result = await call_tool(
        client,
        token,
        "controlled_documents",
        {"product_id": product_id, "include_product_projects": True},
    )

    assert result["isError"] is False, result
    data = result["structuredContent"]
    assert [row["id"] for row in data["checklists"]["items"]] == [checklist["id"]]
    [calculation_row] = data["calculations"]["items"]
    assert calculation_row["id"] == calculation["id"]
    assert calculation_row["project_number"] == "P-MCP-Q"
    assert "results" not in calculation_row
    assert [row["id"] for row in data["sequences"]["items"]] == [sequence["id"]]
    assert data["checklists"]["items"][0]["released_at"] is None
    assert data["checklists"]["items"][0]["creator_full_name"] == "[hidden]"


@pytest.mark.usefixtures("agents_on")
async def test_controlled_documents_hides_another_users_personal_calculation(
    client: httpx.AsyncClient,
    create_user: Callable[..., Awaitable[User]],
    agent_owner: User,
    mint: Callable[..., Awaitable[str]],
) -> None:
    colleague = await create_user(
        username="quality-colleague",
        email="quality-colleague@example.com",
        permissions=[Permission.WRITE_CALCULATIONS],
    )
    await _created(client, colleague, "calculations", _calculation(title="Colleague's own"))
    mine = await _created(client, agent_owner, "calculations", _calculation(title="My own"))
    token = await mint([Permission.USE_MCP])

    result = await call_tool(client, token, "controlled_documents", {"kinds": ["calculations"]})

    assert result["isError"] is False, result
    data = result["structuredContent"]
    assert [row["id"] for row in data["calculations"]["items"]] == [mine["id"]]
    assert set(data) == {"calculations"}
