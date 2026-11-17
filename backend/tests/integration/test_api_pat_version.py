"""
HTTP-level coverage of `GET /api/v1/pat/version` and the `X-Glados-Version`
header on the real app: any valid PAT reads the version and the `pat`
contract minor, a missing token is turned away but still learns the version
from the header, and the web surface carries no such header.
"""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.const import PAT_CONTRACT
from src.modules.platform.const import VERSION
from src.modules.platform.domain.value_objects.permission import Permission

_VERSION_PATH = "/api/v1/pat/version"


@pytest.fixture
async def pat_token(db: AsyncSession, create_user) -> str:
    """A real PAT with no permissions at all, minted through CreatePat."""
    owner = await create_user(
        username="version-reader",
        email="version-reader@example.com",
        permissions=[Permission.WRITE_PAT],
    )
    result = await CreatePat(
        SqlAlchemyPatRepository(db),
        settings_repo=SqlAlchemyAdminSettingsRepository(db),
        uow=SqlAlchemyUnitOfWork(db),
    ).execute(actor=owner, cmd=CreatePatCommand(name="version", permissions=[]))
    return result.token


async def test_any_valid_pat_reads_the_version(client: httpx.AsyncClient, pat_token: str) -> None:
    response = await client.get(_VERSION_PATH, headers={"X-Api-Key": pat_token})

    assert response.status_code == 200
    assert response.json() == {"version": VERSION, "pat_contract": PAT_CONTRACT}
    assert VERSION.startswith(f"{PAT_CONTRACT}.")
    assert response.headers["x-glados-version"] == VERSION


async def test_missing_pat_is_rejected_but_carries_the_version(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(_VERSION_PATH)

    assert response.status_code == 401
    assert response.headers["x-glados-version"] == VERSION


async def test_every_pat_route_carries_the_version(
    client: httpx.AsyncClient, pat_token: str
) -> None:
    response = await client.get("/api/v1/pat/bought-items/", headers={"X-Api-Key": pat_token})

    assert response.status_code == 200
    assert response.headers["x-glados-version"] == VERSION


async def test_web_surface_carries_no_version_header(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/web/version")

    assert "x-glados-version" not in response.headers
