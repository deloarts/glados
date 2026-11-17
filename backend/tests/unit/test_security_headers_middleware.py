"""
Unit tests for SecurityHeadersMiddleware over a minimal FastAPI
app, not the real one: fast, and isolates the middleware's own behaviour
from everything else create_app() wires up.
"""

import httpx
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.responses import Response

from src.modules.platform.adapters.inbound.api.middleware.request_context_middleware import (
    RequestContextMiddleware,
)
from src.modules.platform.adapters.inbound.api.middleware.security_headers_middleware import (
    SecurityHeadersMiddleware,
)


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/ok")
    def ok() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/framed")
    def framed() -> JSONResponse:
        return JSONResponse(content={"status": "ok"}, headers={"X-Frame-Options": "SAMEORIGIN"})

    @app.get("/docs/web")
    def docs() -> HTMLResponse:
        return HTMLResponse("<html></html>")

    @app.get("/file.pdf")
    def pdf() -> Response:
        return Response(b"%PDF-1.7", media_type="application/pdf")

    @app.get("/own-policy")
    def own_policy() -> JSONResponse:
        return JSONResponse(
            content={"status": "ok"}, headers={"Content-Security-Policy": "default-src 'self'"}
        )

    @app.get("/boom")
    def boom() -> dict[str, str]:
        # A raised HTTPException, not a bare exception: Starlette's own
        # ServerErrorMiddleware (an unhandled exception's last resort) sits
        # OUTSIDE every app-registered middleware including this one and
        # writes straight to the raw ASGI `send`, bypassing all of them, an
        # HTTPException instead is turned into a response by
        # ExceptionMiddleware, which sits *inside* SecurityHeadersMiddleware,
        # so that response does pass back out through it, which is the
        # "sits outside exception handling" behaviour this test pins.
        raise HTTPException(status_code=500, detail="kaboom")

    # Same relative order as create_app(): RequestContextMiddleware first,
    # SecurityHeadersMiddleware registered after it.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


async def test_adds_nosniff_and_frame_options():
    client = _client(_make_app())
    response = await client.get("/ok")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["cross-origin-resource-policy"] == "same-site"


async def test_hsts_only_over_https():
    client = _client(_make_app())

    plain = await client.get("/ok")
    assert "strict-transport-security" not in plain.headers

    forwarded = await client.get("/ok", headers={"X-Forwarded-Proto": "https"})
    assert forwarded.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"


async def test_does_not_override_an_existing_header():
    client = _client(_make_app())
    response = await client.get("/framed")

    assert response.headers["x-frame-options"] == "SAMEORIGIN"


async def test_headers_are_present_on_an_error_response():
    """The middleware sits outside exception handling: an endpoint that
    raises still gets a response (Starlette's ExceptionMiddleware produces
    it) that passes back out through the middleware stack."""
    client = _client(_make_app())
    response = await client.get("/boom")

    assert response.status_code == 500
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


async def test_request_id_header_still_present():
    """Regression: X-Request-ID (RequestContextMiddleware) survives sitting
    inside SecurityHeadersMiddleware, ordering did not break it."""
    client = _client(_make_app())
    response = await client.get("/ok")

    assert "x-request-id" in response.headers


async def test_api_responses_get_a_policy_that_allows_nothing():
    client = _client(_make_app())

    for path in ("/ok", "/boom"):
        response = await client.get(path)
        assert (
            response.headers["content-security-policy"]
            == "default-src 'none'; frame-ancestors 'none'"
        )


async def test_swagger_ui_pages_get_no_policy():
    client = _client(_make_app())
    response = await client.get("/docs/web")

    assert "content-security-policy" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_a_pdf_may_use_the_browser_viewer_but_never_sits_in_a_frame():
    client = _client(_make_app())
    response = await client.get("/file.pdf")

    assert response.headers["content-security-policy"] == "frame-ancestors 'none'"


async def test_a_policy_the_route_sets_wins():
    client = _client(_make_app())
    response = await client.get("/own-policy")

    assert response.headers.get_list("content-security-policy") == ["default-src 'self'"]
