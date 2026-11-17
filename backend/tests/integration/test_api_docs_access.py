"""
The Swagger UI pages and the OpenAPI schemas map every route, so outside
debug mode each needs a signed-in web session. The pat pages also take a
personal access token, for the add-in developer's tools. Debug mode keeps
every page open for local development.
"""

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.inbound.api.docs import register_surface_docs
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.domain.value_objects.permission import Permission

_SESSION_ONLY = [
    "/openapi.json",
    "/docs",
    "/api/v1/web/openapi.json",
    "/docs/web",
    "/api/v1/key/openapi.json",
    "/docs/key",
]
_PAT_PAGES = ["/api/v1/pat/openapi.json", "/docs/pat"]


@pytest.mark.parametrize("path", _SESSION_ONLY + _PAT_PAGES)
async def test_an_anonymous_request_is_refused(client: httpx.AsyncClient, path: str) -> None:
    assert (await client.get(path)).status_code == 401


@pytest.mark.parametrize("path", _SESSION_ONLY + _PAT_PAGES)
async def test_any_signed_in_user_reads_the_docs(auth_client, path: str) -> None:
    reader = await auth_client()

    response = await reader.get(path)

    assert response.status_code == 200, response.text


async def test_fastapi_redoc_page_is_gone(auth_client) -> None:
    reader = await auth_client()

    assert (await reader.get("/redoc")).status_code == 404


async def _mint_pat(db: AsyncSession, create_user) -> str:
    owner = await create_user(
        username="addin-dev", email="addin-dev@example.com", permissions=[Permission.WRITE_PAT]
    )
    result = await CreatePat(
        SqlAlchemyPatRepository(db),
        settings_repo=SqlAlchemyAdminSettingsRepository(db),
        uow=SqlAlchemyUnitOfWork(db),
    ).execute(actor=owner, cmd=CreatePatCommand(name="docs", expires_in_days=30))
    return result.token


@pytest.mark.parametrize("path", _PAT_PAGES)
async def test_a_pat_opens_the_pat_docs(
    db: AsyncSession, create_user, client: httpx.AsyncClient, path: str
) -> None:
    token = await _mint_pat(db, create_user)

    response = await client.get(path, headers={"X-Api-Key": token})

    assert response.status_code == 200, response.text


async def test_a_pat_does_not_open_the_web_docs(
    db: AsyncSession, create_user, client: httpx.AsyncClient
) -> None:
    token = await _mint_pat(db, create_user)

    response = await client.get("/api/v1/web/openapi.json", headers={"X-Api-Key": token})

    assert response.status_code == 401


async def test_a_wrong_pat_is_refused(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/pat/openapi.json", headers={"X-Api-Key": "glados_pat_x"})

    assert response.status_code == 401


async def test_debug_mode_keeps_the_docs_open() -> None:
    app = FastAPI(title="Docs", openapi_url=None, docs_url=None, redoc_url=None)
    register_surface_docs(app, debug=True)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as anonymous:
        for path in _SESSION_ONLY + _PAT_PAGES:
            assert (await anonymous.get(path)).status_code == 200, path
