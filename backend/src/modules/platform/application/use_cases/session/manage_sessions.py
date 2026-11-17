"""
Self-service management of the acting user's own sessions, GitHub-style:
list them (current one flagged), end one, or end every other one. Always
scoped to the actor, there is no cross-user path here; an admin ending
someone else's sessions goes through force-logout. Ending sessions is
recorded in the security log.
"""

from uuid import UUID

from src.modules.platform.application.dto.session_dto import CurrentSessionResult
from src.modules.platform.application.dto.session_dto import SessionResult
from src.modules.platform.application.services.login_session import read_session_limits
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.entities.user_session import UserSession
from src.modules.platform.domain.exceptions import SessionNotFoundError
from src.modules.platform.domain.services.session_rules import session_expired
from src.modules.platform.domain.services.session_rules import session_hard_expired
from src.modules.platform.domain.services.session_rules import session_hard_expiry
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


def _to_result(session: UserSession, current_sid: UUID | None) -> SessionResult:
    return SessionResult(
        id=session.id,
        public_id=session.public_id,
        created_at=session.created_at,
        last_seen_at=session.last_seen_at,
        user_agent=session.user_agent,
        ip=session.ip,
        is_current=session.public_id == current_sid,
    )


class GetMySessions:
    def __init__(
        self, session_repo: IUserSessionRepository, settings_repo: IPlatformSettingsRepository
    ) -> None:
        self._sessions = session_repo
        self._settings = settings_repo

    async def execute(self, actor: User, current_sid: UUID | None) -> list[SessionResult]:
        """Live sessions only: the repository already excludes revoked
        rows, and idle-expired or hard-expired ones are dropped here, they are dead in every way that matters,
        just not yet garbage-collected."""
        limits = await read_session_limits(self._settings)
        now = now_utc()
        return [
            _to_result(s, current_sid)
            for s in await self._sessions.list_for_user(actor.id)
            if not session_expired(s.last_seen_at, limits.idle_timeout_minutes, now)
            and not session_hard_expired(
                s.created_at, actor.is_systemuser, now, limits.max_lifetime_days
            )
        ]


class GetCurrentSession:
    """The countdown's source of truth: when the session that made
    this request will hard-expire, plus the server's own clock so the
    client can correct for a skewed one."""

    def __init__(
        self, session_repo: IUserSessionRepository, settings_repo: IPlatformSettingsRepository
    ) -> None:
        self._sessions = session_repo
        self._settings = settings_repo

    async def execute(self, actor: User, current_sid: UUID | None) -> CurrentSessionResult:
        now = now_utc()
        expires_at = None
        # No current_sid, or it names a session that is already gone,
        # shouldn't happen on a session-scoped route, fail safe to "no
        # expiry known" rather than 500.
        session = await self._sessions.get_by_public_id(current_sid) if current_sid else None
        if session is not None and session.user_id == actor.id:
            limits = await read_session_limits(self._settings)
            expires_at = session_hard_expiry(
                session.created_at,
                is_systemuser=actor.is_systemuser,
                max_lifetime_days=limits.max_lifetime_days,
            )
        return CurrentSessionResult(expires_at=expires_at, server_time=now)


class RevokeMySession:
    def __init__(
        self,
        session_repo: IUserSessionRepository,
        *,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._sessions = session_repo
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, actor: User, public_id: UUID) -> None:
        """Scoped by actor.id in the repository call, a guessed public_id
        belonging to someone else 404s exactly like a nonexistent one."""
        if not await self._sessions.revoke_by_public_id(actor.id, public_id):
            raise SessionNotFoundError(f"Session {public_id} not found.")
        await self._audit.record(
            SecurityEventType.SESSION_REVOKED,
            actor=actor,
            target_user=actor,
            detail={"scope": "one", "session": str(public_id)},
        )
        await self._uow.commit()
        log.info(f"Revoked session {public_id}.")


class RevokeMyOtherSessions:
    def __init__(
        self,
        session_repo: IUserSessionRepository,
        *,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._sessions = session_repo
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, actor: User, current_sid: UUID | None) -> int:
        """Sign out everywhere else. Returns the number of sessions
        ended. With no current sid (shouldn't happen on a session-scoped
        route) everything is revoked, the fail-safe direction."""
        count = await self._sessions.revoke_all_for_user_except(actor.id, current_sid)
        if count:
            await self._audit.record(
                SecurityEventType.SESSION_REVOKED,
                actor=actor,
                target_user=actor,
                detail={"scope": "others", "sessions": count},
            )
        await self._uow.commit()
        log.info(f"Revoked {count} other session(s).")
        return count
