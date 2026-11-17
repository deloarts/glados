"""
Coverage for `_persist_all` (src/modules/platform/adapters/inbound/api/middleware/
logging_middleware.py), which writes the HTTP log, API-key usage and PAT
usage through one session opened once per request. This guards against a
`SessionLocal()` call inside one of the three branches, which would
silently open three connections per logged request.
"""

import importlib
import logging
from typing import ClassVar

import httpx
import pytest
from _pytest.logging import LogCaptureFixture
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from src.modules.platform.adapters.inbound.api.middleware import logging_middleware
from src.modules.platform.adapters.inbound.api.middleware.logging_middleware import (
    DatabaseLoggingMiddleware,
)
from src.modules.platform.adapters.inbound.api.middleware.logging_middleware import (
    _extract_session_id,
)
from src.modules.platform.adapters.inbound.api.middleware.logging_middleware import _extract_user_id
from src.modules.platform.adapters.inbound.api.middleware.logging_middleware import _persist_all
from src.modules.platform.adapters.inbound.api.middleware.logging_middleware import _RequestLogData
from src.modules.platform.adapters.outbound.persistence.alembic_imports import model_module_names
from src.modules.platform.adapters.outbound.persistence.models.api_key_model import (
    ApiKeyUsageLogOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.base import Base
from src.modules.platform.adapters.outbound.persistence.models.log_model import LogOrmModel
from src.modules.platform.adapters.outbound.persistence.models.pat_model import PatUsageLogOrmModel
from src.modules.platform.adapters.outbound.persistence.statements import count_rows
from src.modules.platform.const import API_KEY
from src.modules.platform.const import API_PAT
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.security.session_cookie import SESSION_COOKIE
from src.modules.platform.infrastructure.security.token import create_access_token

# Import every model module directly so Base.metadata is guaranteed
# complete for create_all() to resolve every FK, independent of alembic
# wiring (mirrors tests/unit/test_change_tracking.py).
for _module_name in model_module_names():
    importlib.import_module(_module_name)


def _request(headers: dict[str, str]) -> Request:
    """A bare ASGI Request carrying only the given headers, enough for
    Request.headers/.cookies, which is all _session_token reads."""
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


class TestSessionTokenAttribution:
    """_extract_user_id/_extract_session_id feed the audit log's user_id/
    username and the sessions list' is_current flag (via session_id_var).
    Since the M2 cookie migration, a web request may carry no Authorization
    header at all, so these must fall back to the session cookie rather
    than silently attributing the request to nobody."""

    def _token(self, sub: int = 7, sid: str = "11111111-1111-1111-1111-111111111111") -> str:
        return create_access_token(subject=sub, persistent=False, expires_delta=None, sid=sid)

    def test_reads_the_user_id_from_the_bearer_header(self):
        request = _request({"Authorization": f"Bearer {self._token()}"})

        assert _extract_user_id(request) == 7

    def test_reads_the_user_id_from_the_session_cookie_when_no_bearer_header(self):
        request = _request({"Cookie": f"{SESSION_COOKIE}={self._token()}"})

        assert _extract_user_id(request) == 7

    def test_the_bearer_header_wins_over_a_cookie_when_both_are_present(self):
        request = _request(
            {
                "Authorization": f"Bearer {self._token(sub=1)}",
                "Cookie": f"{SESSION_COOKIE}={self._token(sub=2)}",
            }
        )

        assert _extract_user_id(request) == 1

    def test_reads_the_session_id_from_the_session_cookie(self):
        sid = "22222222-2222-2222-2222-222222222222"
        request = _request({"Cookie": f"{SESSION_COOKIE}={self._token(sid=sid)}"})

        assert _extract_session_id(request) == sid

    def test_no_token_anywhere_attributes_nothing(self):
        request = _request({})

        assert _extract_user_id(request) is None
        assert _extract_session_id(request) is None


class _CountingSessionFactory:
    """Wraps a real sessionmaker but counts how many sessions (i.e. DB
    connections) were opened through it."""

    def __init__(self, factory):
        self._factory = factory
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self._factory()


def _data(**overrides):
    base = dict(
        is_write=True,
        method="POST",
        path="/api/v1/web/customers",
        status_code=201,
        user_id=1,
        username="tester",
        request_id="req-1",
        api_key_id=None,
        pat_id=None,
    )
    base.update(overrides)
    return _RequestLogData(**base)


class TestPersistAllUsesOneSession:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.counting_factory = _CountingSessionFactory(
            async_sessionmaker(bind=engine, expire_on_commit=False)
        )
        yield
        await engine.dispose()

    async def _run(self, monkeypatch, data):
        monkeypatch.setattr(logging_middleware, "SessionLocal", self.counting_factory)
        await _persist_all(data)

    async def test_writes_all_three_record_kinds_from_one_session(self, monkeypatch):
        data = _data(is_write=True, api_key_id=42, pat_id=99)

        await self._run(monkeypatch, data)

        assert self.counting_factory.calls == 1
        async with self.counting_factory._factory() as db:
            assert await count_rows(db, select(LogOrmModel)) == 1
            assert await count_rows(db, select(ApiKeyUsageLogOrmModel)) == 1
            assert await count_rows(db, select(PatUsageLogOrmModel)) == 1

    async def test_http_log_only_when_is_write(self, monkeypatch):
        data = _data(is_write=False, api_key_id=7, pat_id=None)

        await self._run(monkeypatch, data)

        assert self.counting_factory.calls == 1
        async with self.counting_factory._factory() as db:
            assert await count_rows(db, select(LogOrmModel)) == 0
            assert await count_rows(db, select(ApiKeyUsageLogOrmModel)) == 1
            assert await count_rows(db, select(PatUsageLogOrmModel)) == 0

    async def test_one_failing_write_does_not_block_the_others(self, monkeypatch):
        """A negative status_code violates the HTTP log's schema-level
        expectations closely enough to prove isolation without reaching
        into SQLAlchemy internals: force the log save to fail and confirm
        the API-key write still lands."""
        data = _data(is_write=True, api_key_id=7, pat_id=None)

        async def _boom(self, entry):
            raise RuntimeError("simulated failure")

        monkeypatch.setattr(
            "src.modules.platform.adapters.outbound.persistence.repositories.log_repository."
            "SqlAlchemyLogRepository.save",
            _boom,
        )

        await self._run(monkeypatch, data)

        async with self.counting_factory._factory() as db:
            assert await count_rows(db, select(LogOrmModel)) == 0
            assert await count_rows(db, select(ApiKeyUsageLogOrmModel)) == 1


def _lookup(table):
    """An async (db, key) lookup over a dict, standing in for the
    repository-backed resolvers; the session is never touched."""

    async def _resolve(db, key):
        return table.get(key)

    return _resolve


def _find_record(records: list[logging.LogRecord], message: str) -> logging.LogRecord:
    for record in records:
        if record.getMessage() == message:
            return record
    raise AssertionError(f"no {message!r} record among {[r.getMessage() for r in records]}")


class TestPatAndApiKeyAttribution:
    """PAT and API-key requests both authenticate with the same X-Api-Key
    header (see auth_deps.py's api_key_header), told apart only by URL
    prefix, and never carry a session bearer/cookie: that's the gap this closes.
    The middleware resolves the acting user itself, the same way it
    resolves a session, rather than through get_current_user_pat's/
    get_current_api_key_user's own contextvar writes (see the module
    docstring for why those never reach here).

    Modelled on tests/unit/test_request_context_middleware.py: a minimal
    FastAPI app wrapping only DatabaseLoggingMiddleware, not the real
    create_app(), with fake resolver callables standing in for the real
    hash-and-repository-lookup ones main.py wires up."""

    _PAT_TOKENS: ClassVar[dict[str, tuple[int, int]]] = {"good-pat": (7, 100)}
    _API_KEY_TOKENS: ClassVar[dict[str, tuple[int, int]]] = {"good-key": (8, 200)}

    def _make_app(self) -> FastAPI:
        app = FastAPI()

        @app.get(f"{API_PAT}/whoami")
        def pat_whoami() -> dict[str, int | str | None]:
            log.info("pat request handled")
            return {
                "user_id": logging_middleware.user_id_var.get(),
                "username": logging_middleware.username_var.get(),
                "pat_id": logging_middleware.pat_id_var.get(),
            }

        @app.get(f"{API_KEY}/whoami")
        def key_whoami() -> dict[str, int | str | None]:
            log.info("key request handled")
            return {
                "user_id": logging_middleware.user_id_var.get(),
                "username": logging_middleware.username_var.get(),
                "api_key_id": logging_middleware.api_key_id_var.get(),
            }

        app.add_middleware(
            DatabaseLoggingMiddleware,
            get_username=_lookup({7: "pat-holder", 8: "key-holder"}),
            resolve_pat=_lookup(self._PAT_TOKENS),
            resolve_api_key=_lookup(self._API_KEY_TOKENS),
        )
        return app

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self._make_app()), base_url="http://testserver"
        )

    async def test_valid_pat_stamps_user_id_and_username(
        self, glados_caplog: LogCaptureFixture
    ) -> None:
        async with self._client() as client:
            resp = await client.get(f"{API_PAT}/whoami", headers={"X-Api-Key": "good-pat"})

        assert resp.status_code == 200
        assert resp.json() == {"user_id": 7, "username": "pat-holder", "pat_id": 100}
        record = _find_record(glados_caplog.records, "pat request handled")
        assert record.user_ctx == "user=pat-holder(id=7)"  # type: ignore[attr-defined]

    async def test_valid_api_key_stamps_user_id_and_username(
        self, glados_caplog: LogCaptureFixture
    ) -> None:
        async with self._client() as client:
            resp = await client.get(f"{API_KEY}/whoami", headers={"X-Api-Key": "good-key"})

        assert resp.status_code == 200
        assert resp.json() == {"user_id": 8, "username": "key-holder", "api_key_id": 200}
        record = _find_record(glados_caplog.records, "key request handled")
        assert record.user_ctx == "user=key-holder(id=8)"  # type: ignore[attr-defined]

    async def test_unknown_pat_leaves_attribution_unset(
        self, glados_caplog: LogCaptureFixture
    ) -> None:
        async with self._client() as client:
            resp = await client.get(f"{API_PAT}/whoami", headers={"X-Api-Key": "not-a-real-token"})

        assert resp.json() == {"user_id": None, "username": None, "pat_id": None}
        record = _find_record(glados_caplog.records, "pat request handled")
        assert record.user_ctx == "-"  # type: ignore[attr-defined]

    async def test_unknown_api_key_leaves_attribution_unset(
        self, glados_caplog: LogCaptureFixture
    ) -> None:
        async with self._client() as client:
            resp = await client.get(f"{API_KEY}/whoami", headers={"X-Api-Key": "not-a-real-token"})

        assert resp.json() == {"user_id": None, "username": None, "api_key_id": None}
        record = _find_record(glados_caplog.records, "key request handled")
        assert record.user_ctx == "-"  # type: ignore[attr-defined]

    async def test_missing_credential_leaves_attribution_unset(self) -> None:
        async with self._client() as client:
            resp = await client.get(f"{API_PAT}/whoami")

        assert resp.json() == {"user_id": None, "username": None, "pat_id": None}

    async def test_a_pat_on_the_api_key_surface_is_not_resolved(self) -> None:
        """A PAT's hash only exists in _PAT_TOKENS, so presenting it on the
        key surface must not resolve, proving the two are looked up
        separately by prefix rather than tried against both stores."""
        async with self._client() as client:
            resp = await client.get(f"{API_KEY}/whoami", headers={"X-Api-Key": "good-pat"})

        assert resp.json() == {"user_id": None, "username": None, "api_key_id": None}

    async def test_the_raw_secret_is_never_logged(self, glados_caplog: LogCaptureFixture) -> None:
        async with self._client() as client:
            await client.get(f"{API_PAT}/whoami", headers={"X-Api-Key": "good-pat"})

        assert not any("good-pat" in record.getMessage() for record in glados_caplog.records)
