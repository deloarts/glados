"""Server-side session validation and JWT lifecycle management."""

from collections.abc import Callable
from uuid import UUID

from src.modules.platform.application.services.login_session import read_session_limits
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InvalidTokenError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.session_rules import last_activity
from src.modules.platform.domain.services.session_rules import last_seen_touch_due
from src.modules.platform.domain.services.session_rules import session_expired
from src.modules.platform.domain.services.session_rules import session_hard_expired
from src.modules.platform.domain.value_objects import token_scope
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class ValidateWebToken:
    """Validates a non-persistent JWT and returns the authenticated User.

    decode_token_fn: wraps infrastructure JWT decode; returns
    (sub, ver, scope, sid) or None.

    Session-scoped tokens must also name a live server-side session row
    via their `sid` claim, the row, not the JWT, is what decides whether
    the session is still alive (revocation, idle timeout and absolute
    lifetime, see domain/services/session_rules.py). Restricted-scope tokens
    (totp_pending/totp_setup) are minted mid-authentication before any
    session exists, so the row check applies only to full sessions.
    """

    def __init__(
        self,
        user_repo: IUserRepository,
        decode_token_fn: Callable[
            [str], tuple[str | None, int | None, str | None, str | None] | None
        ],
        session_repo: IUserSessionRepository,
        settings_repo: IPlatformSettingsRepository,
        uow: IUnitOfWork,
    ) -> None:
        self._users = user_repo
        self._decode = decode_token_fn
        self._sessions = session_repo
        self._settings = settings_repo
        self._uow = uow

    async def execute(
        self,
        token: str,
        *,
        allowed_scopes: frozenset[str | None] = frozenset({token_scope.SESSION}),
        idle_seconds: int | None = None,
        count_as_activity: bool = True,
    ) -> User:
        """Validate a web token and return its user.

        `idle_seconds` is how long ago the user last interacted with the
        page, as the web app reports it; None counts the request itself as
        activity. Only activity moves the session's idle timeout on.
        `count_as_activity=False` checks the session without moving it on,
        for a check the server makes on its own, such as an open live stream.

        `allowed_scopes` defaults to a full session only, so every
        restricted scope is refused unless a caller explicitly opts in.
        Allowlisting this way means a newly-introduced scope is closed on
        every existing route by default, the opposite of blocklisting,
        where one forgotten route turns a half-authenticated token into a
        full session.
        """
        if not token:
            raise InvalidTokenError("Invalid access token")

        decoded = self._decode(token)
        if decoded is None:
            raise InvalidTokenError("Could not validate credentials")

        sub, ver, scope, sid = decoded
        if not sub:
            raise InvalidTokenError("Could not validate credentials")

        if scope not in allowed_scopes:
            raise InvalidTokenError("This token is not valid for that request")

        user = found_or_raise(
            await self._users.get_by_id(int(sub)), UserNotFoundError, f"User #{sub} not found"
        )

        token_ver = ver if ver is not None else 0
        if token_ver != user.token_version:
            raise InvalidTokenError("Session invalidated")

        if scope is token_scope.SESSION:
            await self._check_session(sid, user, idle_seconds, count_as_activity)

        return user

    async def _check_session(
        self, sid: str | None, user: User, idle_seconds: int | None, count_as_activity: bool
    ) -> None:
        if not sid:
            # A session token without a sid names no session to check.
            raise InvalidTokenError("Session invalidated")

        try:
            public_id = UUID(sid)
        except ValueError as e:
            raise InvalidTokenError("Session invalidated") from e

        session = await self._sessions.get_by_public_id(public_id)
        if session is None or session.is_revoked or session.user_id != user.id:
            raise InvalidTokenError("Session invalidated")

        now = now_utc()
        # The absolute lifetime on top of the idle rule below, see
        # session_rules.py.
        limits = await read_session_limits(self._settings)
        if session_hard_expired(
            session.created_at, user.is_systemuser, now, limits.max_lifetime_days
        ):
            raise InvalidTokenError("Session expired")
        if session_expired(session.last_seen_at, limits.idle_timeout_minutes, now):
            raise InvalidTokenError("Session expired")

        # Sliding window: activity is what keeps the session alive, but a
        # write per request would be wasteful, only refresh once the
        # stored value is stale (see session_rules). The stored value moves
        # to when the user last did something, never to a request the app
        # sent on its own.
        active_at = last_activity(now, idle_seconds)
        if count_as_activity and last_seen_touch_due(session.last_seen_at, active_at):
            await self._sessions.touch_last_seen(session.public_id, active_at)
            # Committed right away, before the route runs, so activity keeps
            # the session alive even when the request then fails or never
            # writes anything itself.
            await self._uow.commit()
