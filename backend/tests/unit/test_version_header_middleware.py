"""
Unit tests for VersionHeaderMiddleware over a minimal FastAPI app, and for
`contract_minor`, which names the `pat` contract a version serves.
"""

import httpx
import pytest
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from src.modules.platform.adapters.inbound.api.middleware.version_header_middleware import (
    VersionHeaderMiddleware,
)
from src.modules.platform.const import API_KEY
from src.modules.platform.const import API_PAT
from src.modules.platform.const import API_PUBLIC
from src.modules.platform.const import contract_minor


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get(f"{API_PAT}/things")
    def things() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(f"{API_PAT}/denied")
    def denied() -> dict[str, str]:
        raise HTTPException(status_code=401, detail="no token")

    @app.get(f"{API_PAT}/own")
    def own() -> JSONResponse:
        return JSONResponse(content={}, headers={"X-Glados-Version": "9.9.9"})

    @app.get(f"{API_KEY}/things")
    def key_things() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(f"{API_PUBLIC}/things")
    def public_things() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/web/things")
    def web_things() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/patterns")
    def lookalike() -> dict[str, str]:
        return {"status": "ok"}

    app.add_middleware(VersionHeaderMiddleware, version="1.2.3")
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


async def test_pat_response_carries_the_version() -> None:
    response = await _client(_make_app()).get(f"{API_PAT}/things")

    assert response.status_code == 200
    assert response.headers["x-glados-version"] == "1.2.3"


@pytest.mark.parametrize("prefix", [API_KEY, API_PUBLIC])
async def test_the_other_contract_surfaces_carry_the_version(prefix: str) -> None:
    """The pat snapshot bundles the key and public surfaces, which the
    add-ins call, so they name the server version too."""
    response = await _client(_make_app()).get(f"{prefix}/things")

    assert response.headers["x-glados-version"] == "1.2.3"


async def test_pat_error_response_carries_the_version() -> None:
    response = await _client(_make_app()).get(f"{API_PAT}/denied")

    assert response.status_code == 401
    assert response.headers["x-glados-version"] == "1.2.3"


async def test_unknown_pat_route_carries_the_version() -> None:
    """A client built for a newer minor learns the version from the 404 of
    a route this backend does not have yet."""
    response = await _client(_make_app()).get(f"{API_PAT}/missing")

    assert response.status_code == 404
    assert response.headers["x-glados-version"] == "1.2.3"


async def test_header_set_by_the_route_wins() -> None:
    response = await _client(_make_app()).get(f"{API_PAT}/own")

    assert response.headers.get_list("x-glados-version") == ["9.9.9"]


@pytest.mark.parametrize("path", ["/api/v1/web/things", "/api/v1/patterns"])
async def test_other_surfaces_carry_no_version(path: str) -> None:
    response = await _client(_make_app()).get(path)

    assert response.status_code == 200
    assert "x-glados-version" not in response.headers


@pytest.mark.parametrize(
    ("version", "minor"), [("1.2.3", "1.2"), ("0.1.0", "0.1"), ("1.10.0", "1.10")]
)
def test_contract_minor(version: str, minor: str) -> None:
    assert contract_minor(version) == minor


def test_contract_minor_rejects_a_bare_major() -> None:
    with pytest.raises(ValueError, match=r"major\.minor"):
        contract_minor("1")
