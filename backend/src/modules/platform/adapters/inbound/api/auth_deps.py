"""Auth schemes and current-user resolution dependencies.

The web session travels in an httponly cookie that JavaScript cannot read.
A bearer header is also accepted, for tests and the TOTP setup-token bridge.

A bearer token carries no CSRF risk, but the cookie does, so an unsafe
method authenticated by cookie must carry `X-Requested-With: glados`.
Forms and image tags cannot set a custom header, and a script that could
would have to run on an origin CORS already allows.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from fastapi import Security
from fastapi import status
from fastapi.security import APIKeyHeader
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.inbound.api.deps.database import get_db
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_api_key_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_pat_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_platform_settings_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_session_repo
from src.modules.platform.adapters.outbound.persistence.changer_tracking import bind_acting_user
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.application.services.validate_api_key import ValidateApiKey
from src.modules.platform.application.use_cases.pat.validate_pat import ValidatePat
from src.modules.platform.application.use_cases.user.validate_web_token import ValidateWebToken
from src.modules.platform.const import API_AUTH
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InactiveUserError
from src.modules.platform.domain.exceptions import InvalidTokenError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.maintenance_policy import assert_maintenance_allows
from src.modules.platform.domain.value_objects import token_scope
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.label_languages import set_label_languages
from src.modules.platform.infrastructure.logging.context import api_key_id_var
from src.modules.platform.infrastructure.logging.context import pat_id_var
from src.modules.platform.infrastructure.security.api_key import hash_api_key
from src.modules.platform.infrastructure.security.pat import hash_pat
from src.modules.platform.infrastructure.security.session_cookie import SESSION_COOKIE
from src.modules.platform.infrastructure.security.token import get_token_payload
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.api_key_repository import IApiKeyRepository
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

# ── Maintenance mode ────────────────────────────────────────────────────


async def _enforce_maintenance(
    user: User, request: Request, admin_settings_repo: IPlatformSettingsRepository
) -> None:
    """Gates every authenticated surface on maintenance mode from one
    place. The client IP is `request.client.host`, which the server resolves
    from X-Forwarded-For only for a trusted proxy (gunicorn_conf.py).
    """
    assert_maintenance_allows(
        user,
        await admin_settings_repo.get_maintenance(),
        request.client.host if request.client else None,
    )


# ── Auth schemes ──────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{API_AUTH}/login/access-token",
    auto_error=False,
)
api_key_header = APIKeyHeader(name="X-Api-Key", auto_error=False)


# ── Token bridge helpers ──────────────────────────────────────────────


def _decode_web_token(
    token: str,
) -> tuple[str | None, int | None, str | None, str | None] | None:
    payload = get_token_payload(token, persistent=False)
    if payload is None:
        return None
    return (
        str(payload.sub) if payload.sub is not None else None,
        payload.ver,
        payload.scope,
        payload.sid,
    )


def _resolve_session_token(request: Request, bearer: str) -> tuple[str, bool]:
    """The session token and whether it came from the cookie. The header
    wins when present."""
    if bearer:
        return bearer, False
    return request.cookies.get(SESSION_COOKIE) or "", True


# ── CSRF ─────────────────────────────────────────────────────────────

_CSRF_PROTECTED_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CSRF_HEADER_NAME = "X-Requested-With"
CSRF_HEADER_VALUE = "glados"


def require_csrf_header(request: Request) -> None:
    """Rejects an unsafe request without the CSRF header."""
    if request.method not in _CSRF_PROTECTED_METHODS:
        return
    if request.headers.get(CSRF_HEADER_NAME) != CSRF_HEADER_VALUE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing CSRF header")


# ── Auth resolution ───────────────────────────────────────────────────

# Seconds since the user last interacted with the page, sent by the web app
# with every request so its own polls do not keep a session alive.
IDLE_HEADER_NAME = "X-Glados-Idle-Seconds"


def _reported_idle_seconds(request: Request) -> int | None:
    """The idle report of the request, or None when it has none or it is unreadable."""
    raw = request.headers.get(IDLE_HEADER_NAME)
    if raw is None or not raw.isdigit():
        return None
    return int(raw)


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    user_repo: IUserRepository = Depends(get_user_repo),
    session_repo: IUserSessionRepository = Depends(get_user_session_repo),
    admin_settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> User:
    resolved_token, from_cookie = _resolve_session_token(request, token)
    use_case = ValidateWebToken(
        user_repo=user_repo,
        decode_token_fn=_decode_web_token,
        session_repo=session_repo,
        settings_repo=admin_settings_repo,
        uow=uow,
    )
    # session_id_var is set earlier, by the logging middleware.
    try:
        user = await use_case.execute(resolved_token, idle_seconds=_reported_idle_seconds(request))
    except InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        ) from e
    if from_cookie:
        require_csrf_header(request)
    await _enforce_maintenance(user, request, admin_settings_repo)
    bind_acting_user(db, user.id)
    # Server-composed texts that include a catalogue label read it in the
    # user's language (see label_languages.py).
    general = await admin_settings_repo.get_general()
    set_label_languages([user.language.value, general.default_language.value])
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return current_user


# Checks the session a live stream was opened with again and answers the
# user's current permissions, or None once the session is no longer valid.
LiveSessionCheck = Callable[[], Awaitable[frozenset[str] | None]]


def get_live_session_check(
    request: Request, token: str = Depends(oauth2_scheme)
) -> LiveSessionCheck:
    """A check the live stream runs while it is open. The request's own
    database session is closed once the stream starts, so each check opens
    a short one of its own. It never counts as activity, so an open tab
    does not keep an idle session alive."""
    resolved_token, _ = _resolve_session_token(request, token)

    async def check() -> frozenset[str] | None:
        async with SessionLocal() as db:
            use_case = ValidateWebToken(
                user_repo=get_user_repo(db),
                decode_token_fn=_decode_web_token,
                session_repo=get_user_session_repo(db),
                settings_repo=get_platform_settings_repo(db),
                uow=get_unit_of_work(db),
            )
            try:
                user = await use_case.execute(resolved_token, count_as_activity=False)
            except (InvalidTokenError, UserNotFoundError):
                return None
            if not user.is_active:
                return None
            return frozenset(user.effective_permissions)

    return check


@dataclass(frozen=True)
class TotpEnrolmentActor:
    """Who is enrolling. A forced enroller arrives by setup token and gets a
    real session from /confirm instead of a second login.
    """

    user: User
    via_setup_token: bool


async def get_totp_enrolment_actor(
    request: Request,
    token: str = Depends(oauth2_scheme),
    user_repo: IUserRepository = Depends(get_user_repo),
    session_repo: IUserSessionRepository = Depends(get_user_session_repo),
    admin_settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> TotpEnrolmentActor:
    """Accepts a session or, for enrolment forced at login, a setup token.
    Only the enrolment endpoints use it.
    """
    resolved_token, from_cookie = _resolve_session_token(request, token)
    use_case = ValidateWebToken(
        user_repo=user_repo,
        decode_token_fn=_decode_web_token,
        session_repo=session_repo,
        settings_repo=admin_settings_repo,
        uow=uow,
    )
    try:
        user = await use_case.execute(
            resolved_token,
            allowed_scopes=frozenset({token_scope.SESSION, token_scope.TOTP_SETUP}),
            idle_seconds=_reported_idle_seconds(request),
        )
    except InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        ) from e

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    if from_cookie:
        require_csrf_header(request)
    await _enforce_maintenance(user, request, admin_settings_repo)

    decoded = _decode_web_token(resolved_token)
    return TotpEnrolmentActor(user=user, via_setup_token=bool(decoded and decoded[2]))


async def get_current_user_pat(
    request: Request,
    token: str = Security(api_key_header),
    user_repo: IUserRepository = Depends(get_user_repo),
    pat_repo: IPatRepository = Depends(get_pat_repo),
    admin_settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> User:
    use_case = ValidatePat(pat_repo=pat_repo, user_repo=user_repo, hash_fn=hash_pat)
    try:
        user, pat_id = await use_case.execute(token or "")
    except InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        ) from e
    except InactiveUserError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user") from e

    # Set before the maintenance check, so a blocked request is attributed.
    pat_id_var.set(pat_id)
    await _enforce_maintenance(user, request, admin_settings_repo)
    bind_acting_user(db, user.id)
    return user


async def get_current_api_key_user(
    request: Request,
    token: str = Security(api_key_header),
    user_repo: IUserRepository = Depends(get_user_repo),
    key_repo: IApiKeyRepository = Depends(get_api_key_repo),
    admin_settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> User:
    if not (await admin_settings_repo.get_security()).enable_api_key_auth:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="API key authentication is disabled"
        )

    use_case = ValidateApiKey(key_repo=key_repo, user_repo=user_repo, hash_fn=hash_api_key)
    try:
        user, key_id = await use_case.execute(token or "")
    except InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        ) from e
    except InactiveUserError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user") from e

    # Set before the maintenance check, so a blocked request is attributed.
    api_key_id_var.set(key_id)
    # A terminal key may only register a display. The key router has routes
    # that accept any valid key without checking a permission, so a terminal
    # key is refused here before any of them runs.
    if Permission.CONNECT_TERMINALS in user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A terminal key cannot be used on the key API",
        )
    await _enforce_maintenance(user, request, admin_settings_repo)
    bind_acting_user(db, user.id)
    return user
