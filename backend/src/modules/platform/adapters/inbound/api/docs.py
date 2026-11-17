"""
Per-surface Swagger UI pages.

FastAPI generates a single OpenAPI schema for the whole app. To give each
client surface (web, pat, key) its own focused "/docs/<surface>" page, we
derive a filtered schema per surface from the full schema, keeping only the
operations tagged for that surface, and serve it via its own Swagger UI.

Auth endpoints live under /api/v1/auth but are tagged per surface
(web/auth, pat/auth, key/auth, see v1/auth/router.py), so they show up on
the matching surface's docs page. /docs and /openapi.json serve the whole,
unfiltered schema; FastAPI's own routes for them stay off (see main.py), so
every docs route passes the same gate.

Outside debug mode the schema maps every route an attacker could try, so
each page and schema needs a signed-in web session. The pat pages also
accept a personal access token in X-Api-Key, so an add-in developer's tools
can fetch the schema they build against without a browser session.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sequence
from typing import Any

from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi import Security
from fastapi import status
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.params import Depends as DependsParam
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.inbound.api.auth_deps import api_key_header
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.adapters.inbound.api.auth_deps import oauth2_scheme
from src.modules.platform.adapters.inbound.api.deps.database import get_db
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_pat_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_platform_settings_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_session_repo
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

SURFACES = {
    "web": "Glados - Web API",
    "pat": "Glados - Personal Access Token API",
    "key": "Glados - API Key API",
}


async def _require_session(_: User = Depends(get_current_active_user)) -> None:
    """Any signed-in web user may read the docs."""


async def _require_session_or_pat(
    request: Request,
    pat: str = Security(api_key_header),
    token: str = Depends(oauth2_scheme),
    user_repo: IUserRepository = Depends(get_user_repo),
    session_repo: IUserSessionRepository = Depends(get_user_session_repo),
    pat_repo: IPatRepository = Depends(get_pat_repo),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> None:
    """A personal access token in X-Api-Key, or else a signed-in web session."""
    if pat:
        await get_current_user_pat(
            request=request,
            token=pat,
            user_repo=user_repo,
            pat_repo=pat_repo,
            admin_settings_repo=settings_repo,
            db=db,
        )
        return
    user = await get_current_user(
        request=request,
        token=token,
        user_repo=user_repo,
        session_repo=session_repo,
        admin_settings_repo=settings_repo,
        uow=uow,
        db=db,
    )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")


def _gate(surface: str, *, debug: bool) -> Sequence[DependsParam]:
    """The dependencies that guard one docs page and its schema. Debug mode
    keeps them open for local development."""
    if debug:
        return []
    if surface == "pat":
        return [Depends(_require_session_or_pat)]
    return [Depends(_require_session)]


def _filtered_openapi(app: FastAPI, tag_prefix: str) -> dict[str, Any]:
    schema = app.openapi()
    paths: dict[str, Any] = {}
    for path, operations in schema.get("paths", {}).items():
        kept = {
            method: operation
            for method, operation in operations.items()
            if any(tag.startswith(tag_prefix) for tag in operation.get("tags", []))
        }
        if kept:
            paths[path] = kept
    return {**schema, "paths": paths}


def _make_openapi_route(app: FastAPI, tag_prefix: str) -> Callable[[], Awaitable[dict[str, Any]]]:
    async def _openapi() -> dict[str, Any]:
        return _filtered_openapi(app, tag_prefix)

    return _openapi


def _make_docs_route(openapi_url: str, title: str) -> Callable[[], Awaitable[HTMLResponse]]:
    async def _docs() -> HTMLResponse:
        return get_swagger_ui_html(openapi_url=openapi_url, title=title)

    return _docs


def _make_full_openapi_route(app: FastAPI) -> Callable[[], Awaitable[dict[str, Any]]]:
    async def _openapi() -> dict[str, Any]:
        return app.openapi()

    return _openapi


def register_surface_docs(app: FastAPI, *, debug: bool) -> None:
    """Register /docs/<surface> and its filtered openapi.json for web, pat and
    key, plus /docs and /openapi.json for the whole schema. Outside debug
    mode each needs a signed-in session, the pat pages a PAT as an
    alternative."""

    app.add_api_route(
        "/openapi.json",
        _make_full_openapi_route(app),
        include_in_schema=False,
        dependencies=_gate("full", debug=debug),
    )
    app.add_api_route(
        "/docs",
        _make_docs_route("/openapi.json", app.title),
        include_in_schema=False,
        dependencies=_gate("full", debug=debug),
    )

    for surface, title in SURFACES.items():
        openapi_url = f"/api/v1/{surface}/openapi.json"
        gate = _gate(surface, debug=debug)

        app.add_api_route(
            openapi_url,
            _make_openapi_route(app, f"{surface}/"),
            include_in_schema=False,
            dependencies=gate,
        )
        app.add_api_route(
            f"/docs/{surface}",
            _make_docs_route(openapi_url, title),
            include_in_schema=False,
            dependencies=gate,
        )
