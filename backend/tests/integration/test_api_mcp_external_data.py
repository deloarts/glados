"""
The CAD & external data tools of the MCP surface: the EPLAN Data Portal
lookup over HTTP against a fake portal, with the Data Portal permission it
shares with the web's search.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Iterator
from datetime import UTC
from datetime import datetime
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
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._mcp_helpers import call_tool
from tests.integration._mcp_helpers import list_tool_names
from tests.integration._mcp_helpers import mint_agent_token
from tests.integration._mcp_helpers import save_agent_settings

NOW = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


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


PARTS = {1: _part(1, "19210"), 2: _part(2, "19211"), 3: _part(3, "19212")}


class _FakePortal:
    def __init__(self) -> None:
        self.searches: list[tuple[str, int]] = []

    def factory(self, connection: EdpConnection) -> "_FakePortal":
        return self

    async def search(self, query: str, limit: int) -> list[EdpPart]:
        self.searches.append((query, limit))
        return list(PARTS.values())[:limit]

    async def check_numbers(self, numbers: list[str]) -> list[EdpNumberMatch]:
        table = {"19210": (1,)}
        return [EdpNumberMatch(search=n, part_ids=table.get(n, ())) for n in numbers]

    async def get_parts(self, part_ids: list[int]) -> list[EdpPart]:
        return [PARTS[i] for i in part_ids if i in PARTS]


@pytest.fixture(autouse=True)
def portal() -> Iterator[_FakePortal]:
    fake = _FakePortal()
    app.dependency_overrides[get_eplan_data_portal_factory] = lambda: fake.factory
    yield fake
    app.dependency_overrides.pop(get_eplan_data_portal_factory, None)


@pytest.fixture(autouse=True)
async def agents_on(db: AsyncSession) -> None:
    await save_agent_settings(db)
    await SqlAlchemyAdminSettingsRepository(db).save_edp(
        AdminEdpSettings(id=1, enabled=True, pat="token")
    )
    await db.commit()


@pytest.fixture
async def agent_owner(create_user: Callable[..., Awaitable[User]]) -> User:
    return await create_user(
        username="planner",
        email="planner@example.com",
        permissions=[Permission.WRITE_PAT, Permission.USE_MCP, Permission.USE_DATA_PORTAL],
    )


@pytest.fixture
def mint(db: AsyncSession, agent_owner: User) -> Callable[..., Awaitable[str]]:
    async def _mint(permissions: list[str]) -> str:
        return await mint_agent_token(db, agent_owner, permissions)

    return _mint


def _text(result: dict[str, Any]) -> str:
    return str(result["content"][0]["text"])


# ── edp_lookup ────────────────────────────────────────────────────────


async def test_edp_lookup_matches_an_order_number(
    client: httpx.AsyncClient, mint: Callable[..., Awaitable[str]]
) -> None:
    token = await mint([Permission.USE_MCP, Permission.USE_DATA_PORTAL])

    result = await call_tool(client, token, "edp_lookup", {"query": "19210"})

    assert result["isError"] is False, _text(result)
    [hit] = result["structuredContent"]["hits"]
    assert hit["part"]["part_id"] == 1
    assert hit["draft"]["order_code_1"] == "19210"
    assert hit["existing_item"] is None


async def test_edp_lookup_search_passes_its_limit_to_the_portal(
    client: httpx.AsyncClient, mint: Callable[..., Awaitable[str]], portal: _FakePortal
) -> None:
    token = await mint([Permission.USE_MCP, Permission.USE_DATA_PORTAL])

    result = await call_tool(
        client, token, "edp_lookup", {"query": "cylinder", "mode": "search", "limit": 2}
    )

    assert result["isError"] is False, _text(result)
    assert len(result["structuredContent"]["hits"]) == 2
    assert portal.searches == [("cylinder", 2)]


async def test_edp_lookup_is_hidden_without_the_data_portal_permission(
    client: httpx.AsyncClient, mint: Callable[..., Awaitable[str]], portal: _FakePortal
) -> None:
    token = await mint([Permission.USE_MCP])

    assert "edp_lookup" not in await list_tool_names(client, token)
    result = await call_tool(client, token, "edp_lookup", {"query": "19210"})
    assert result["isError"] is True
    assert portal.searches == []


async def test_edp_lookup_is_hidden_with_only_the_bought_item_write_permission(
    client: httpx.AsyncClient,
    create_user: Callable[..., Awaitable[User]],
    db: AsyncSession,
    portal: _FakePortal,
) -> None:
    owner = await create_user(
        username="buyer",
        email="buyer@example.com",
        permissions=[Permission.WRITE_PAT, Permission.USE_MCP, Permission.WRITE_BOUGHT_ITEMS],
    )
    token = await mint_agent_token(db, owner, [Permission.USE_MCP, Permission.WRITE_BOUGHT_ITEMS])

    assert "edp_lookup" not in await list_tool_names(client, token)
    result = await call_tool(client, token, "edp_lookup", {"query": "cylinder", "mode": "search"})
    assert result["isError"] is True
    assert portal.searches == []
