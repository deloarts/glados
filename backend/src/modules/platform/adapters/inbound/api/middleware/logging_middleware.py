"""Persists every write request to log_table and sets the request context
variables, so log records carry the user and, for PAT and API-key requests,
the credential.

Attribution is resolved before the app runs and is best effort: a revoked
token still attributes the request to whoever it names, which is fine for an
audit trail but never proof of who acted. A pure ASGI middleware, so
streaming responses pass through untouched; logging failures are swallowed
so they never break a request.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.types import ASGIApp
from starlette.types import Message
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

from src.modules.platform.adapters.outbound.persistence.repositories.api_key_repository import (
    SqlAlchemyApiKeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.api_key_usage_log_repository import (
    SqlAlchemyApiKeyUsageLogRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.log_repository import (
    SqlAlchemyLogRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.pat_usage_log_repository import (
    SqlAlchemyPatUsageLogRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.const import API_KEY
from src.modules.platform.const import API_PAT
from src.modules.platform.domain.entities.api_key_usage_log import ApiKeyUsageLogEntry
from src.modules.platform.domain.entities.log_entry import LogEntry
from src.modules.platform.domain.entities.pat_usage_log import PatUsageLogEntry
from src.modules.platform.infrastructure.logging.context import api_key_id_var
from src.modules.platform.infrastructure.logging.context import pat_id_var
from src.modules.platform.infrastructure.logging.context import request_id_var
from src.modules.platform.infrastructure.logging.context import session_id_var
from src.modules.platform.infrastructure.logging.context import user_id_var
from src.modules.platform.infrastructure.logging.context import username_var
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.security.api_key import hash_api_key
from src.modules.platform.infrastructure.security.pat import hash_pat
from src.modules.platform.infrastructure.security.session_cookie import SESSION_COOKIE
from src.modules.platform.infrastructure.security.token import get_subject_from_token
from src.modules.platform.infrastructure.security.token import get_token_payload
from src.shared_kernel.domain.services.clock import now_utc

_SKIP_PATHS = {"/health", "/ready", "/metrics"}
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

#: (user_id, credential_id) for a resolved PAT/API key, or None when the
#: presented secret doesn't hash to a known row.
_CredentialActor = tuple[int, int] | None

UsernameLookup = Callable[[AsyncSession, int], Awaitable[str | None]]
CredentialLookup = Callable[[AsyncSession, str], Awaitable[_CredentialActor]]


async def lookup_username(db: AsyncSession, user_id: int) -> str | None:
    user = await SqlAlchemyUserRepository(db).get_by_id(user_id)
    return user.username if user else None


async def lookup_pat_actor(db: AsyncSession, raw_token: str) -> _CredentialActor:
    token = await SqlAlchemyPatRepository(db).get_by_token_hash(hash_pat(raw_token))
    return (token.user_id, token.id) if token else None


async def lookup_api_key_actor(db: AsyncSession, raw_token: str) -> _CredentialActor:
    key = await SqlAlchemyApiKeyRepository(db).get_by_token_hash(hash_api_key(raw_token))
    return (key.user_id, key.id) if key else None


@dataclass(frozen=True)
class _RequestLogData:
    is_write: bool
    method: str
    path: str
    status_code: int
    user_id: int | None
    username: str | None
    request_id: str | None
    api_key_id: int | None
    pat_id: int | None


async def _rollback_quietly(db: AsyncSession) -> None:
    """Clears a failed write so the next one can still use the session."""
    try:
        await db.rollback()
    except Exception:
        log.warning(
            "Rollback after a failed audit write failed.", exc_info=True, extra={"_skip_db": True}
        )


async def _persist_all(data: _RequestLogData) -> None:
    """Writes the HTTP log entry plus API-key/PAT usage entries from a
    single DB session. Each write is committed on its own inside its own
    try/except, so one failing persist doesn't prevent the others."""
    async with SessionLocal() as db:
        uow = SqlAlchemyUnitOfWork(db)
        if data.is_write:
            try:
                await SqlAlchemyLogRepository(db).save(
                    LogEntry(
                        id=0,
                        timestamp=now_utc(),
                        user_id=data.user_id,
                        username=data.username,
                        level="HTTP",
                        message=None,
                        method=data.method,
                        path=data.path,
                        status_code=data.status_code,
                        request_id=data.request_id,
                    )
                )
                await uow.commit()
            except Exception:
                log.exception(
                    "Failed to persist HTTP log entry for %s %s.",
                    data.method,
                    data.path,
                    extra={"_skip_db": True},
                )
                await _rollback_quietly(db)

        # Credential usage is logged for every method, not just writes.
        if data.api_key_id is not None:
            try:
                await SqlAlchemyApiKeyUsageLogRepository(db).append(
                    ApiKeyUsageLogEntry(
                        id=0,
                        key_id=data.api_key_id,
                        called_at=now_utc(),
                        method=data.method,
                        path=data.path,
                        status_code=data.status_code,
                    )
                )
                await uow.commit()
            except Exception:
                log.exception(
                    "Failed to persist API key usage log entry for key #%s (%s %s).",
                    data.api_key_id,
                    data.method,
                    data.path,
                    extra={"_skip_db": True},
                )
                await _rollback_quietly(db)

        if data.pat_id is not None:
            try:
                await SqlAlchemyPatUsageLogRepository(db).append(
                    PatUsageLogEntry(
                        id=0,
                        pat_id=data.pat_id,
                        called_at=now_utc(),
                        method=data.method,
                        path=data.path,
                        status_code=data.status_code,
                    )
                )
                await uow.commit()
            except Exception:
                log.exception(
                    "Failed to persist PAT usage log entry for PAT #%s (%s %s).",
                    data.pat_id,
                    data.method,
                    data.path,
                    extra={"_skip_db": True},
                )
                await _rollback_quietly(db)


def _session_token(request: Request) -> str | None:
    """The request's session token, resolved like auth_deps.py does."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer ") :]
    return request.cookies.get(SESSION_COOKIE)


def _extract_user_id(request: Request) -> int | None:
    """The token's claimed subject, unverified. Fine for the audit trail,
    but never to be trusted as the acting user."""
    token = _session_token(request)
    if not token:
        return None
    subject = get_subject_from_token(token, persistent=False) or get_subject_from_token(
        token, persistent=True
    )
    try:
        return int(subject) if subject else None
    except (ValueError, TypeError):
        return None


def _extract_session_id(request: Request) -> str | None:
    """The token's claimed `sid`, unverified here; consumers act on it only
    after authentication validated the same token."""
    token = _session_token(request)
    if not token:
        return None
    payload = get_token_payload(token, persistent=False)
    return payload.sid if payload else None


def _credential_token(request: Request) -> str | None:
    """The secret of a PAT or API-key request; both use the same header."""
    return request.headers.get("X-Api-Key") or None


async def _resolve_credential_actor(
    db: AsyncSession,
    request: Request,
    resolve_pat: CredentialLookup,
    resolve_api_key: CredentialLookup,
) -> tuple[int | None, int | None, int | None]:
    """Best-effort (user_id, pat_id, api_key_id), chosen by URL prefix
    since both surfaces share the header. Secrets are never logged."""
    token = _credential_token(request)
    if token is None:
        return None, None, None

    path = request.url.path
    if path.startswith(API_PAT):
        resolved = await resolve_pat(db, token)
        if resolved is not None:
            user_id, pat_id = resolved
            return user_id, pat_id, None
    elif path.startswith(API_KEY):
        resolved = await resolve_api_key(db, token)
        if resolved is not None:
            user_id, api_key_id = resolved
            return user_id, None, api_key_id

    return None, None, None


def _needs_credential_lookup(request: Request) -> bool:
    path = request.url.path
    return _credential_token(request) is not None and (
        path.startswith(API_PAT) or path.startswith(API_KEY)
    )


class DatabaseLoggingMiddleware:
    """The lookups default to the real repositories; tests pass stand-ins."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        get_username: UsernameLookup = lookup_username,
        resolve_pat: CredentialLookup = lookup_pat_actor,
        resolve_api_key: CredentialLookup = lookup_api_key_actor,
    ) -> None:
        self._app = app
        self._get_username = get_username
        self._resolve_pat = resolve_pat
        self._resolve_api_key = resolve_api_key

    async def _resolve_actor(
        self, request: Request, user_id: int | None
    ) -> tuple[int | None, int | None, int | None, str | None]:
        """(user_id, pat_id, api_key_id, username), all from one session.
        A failing lookup leaves the values it would have produced unset."""
        pat_id: int | None = None
        api_key_id: int | None = None
        username: str | None = None
        if user_id is None and not _needs_credential_lookup(request):
            return None, None, None, None
        async with SessionLocal() as db:
            if user_id is None:
                try:
                    user_id, pat_id, api_key_id = await _resolve_credential_actor(
                        db, request, self._resolve_pat, self._resolve_api_key
                    )
                except Exception:
                    log.warning(
                        "Failed to resolve the credential of %s %s.",
                        request.method,
                        request.url.path,
                        exc_info=True,
                        extra={"_skip_db": True},
                    )
                    return None, None, None, None
            if user_id is not None:
                try:
                    username = await self._get_username(db, user_id)
                except Exception:
                    log.warning(
                        "Failed to resolve username for user #%s.",
                        user_id,
                        exc_info=True,
                        extra={"_skip_db": True},
                    )
        return user_id, pat_id, api_key_id, username

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request = Request(scope)
        try:
            user_id, pat_id, api_key_id, username = await self._resolve_actor(
                request, _extract_user_id(request)
            )
        except Exception:
            log.warning("Request attribution failed.", exc_info=True, extra={"_skip_db": True})
            user_id, pat_id, api_key_id, username = None, None, None, None

        # Populate context vars so downstream log lines carry the user, and
        # (for PAT/API-key requests) the credential that authenticated it.
        uid_token = user_id_var.set(user_id)
        uname_token = username_var.set(username)
        sid_token = session_id_var.set(_extract_session_id(request))
        pat_token = pat_id_var.set(pat_id)
        api_key_token = api_key_id_var.set(api_key_id)

        status_code: int | None = None

        async def send_capturing_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self._app(scope, receive, send_capturing_status)

            if status_code is None:
                return
            method = request.method
            path = request.url.path
            rid = request_id_var.get()
            data = _RequestLogData(
                is_write=method in _WRITE_METHODS and path not in _SKIP_PATHS,
                method=method,
                path=path,
                status_code=status_code,
                user_id=user_id,
                username=username,
                request_id=rid if rid and rid != "-" else None,
                api_key_id=api_key_id_var.get(),
                pat_id=pat_id_var.get(),
            )
            if data.is_write or data.api_key_id is not None or data.pat_id is not None:
                try:
                    await _persist_all(data)
                except Exception:
                    log.exception(
                        "Failed to persist the audit rows for %s %s.",
                        method,
                        path,
                        extra={"_skip_db": True},
                    )
        finally:
            user_id_var.reset(uid_token)
            username_var.reset(uname_token)
            session_id_var.reset(sid_token)
            pat_id_var.reset(pat_token)
            api_key_id_var.reset(api_key_token)
