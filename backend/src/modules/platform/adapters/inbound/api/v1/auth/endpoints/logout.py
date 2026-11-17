"""
Ends the caller's web session and clears its cookie. Deliberately not
gated behind the ordinary session dependency: a session that has already
expired or been revoked elsewhere must still have its cookie cleared, and
refusing to touch it here (a 401) would leave that stale cookie sitting
in the browser. The CSRF header is still required, unconditionally, this
endpoint is cookie-only, browsers are its only caller, so there is no
bearer-token case that would need exempting (see auth_deps.py's module
docstring for the general cookie/bearer/CSRF design). Ending a live
session is recorded in the security log.
"""

from uuid import UUID

from fastapi import Depends
from fastapi import Request
from fastapi import Response
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import require_csrf_header
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_session_repo
from src.modules.platform.adapters.inbound.api.deps.services import get_security_audit
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.security.session_cookie import SESSION_COOKIE
from src.modules.platform.infrastructure.security.session_cookie import clear_session_cookie
from src.modules.platform.infrastructure.security.token import get_token_payload
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

router = APIRouter()


@router.post("/logout", response_model=dict)
async def logout(
    request: Request,
    response: Response,
    session_repo: IUserSessionRepository = Depends(get_user_session_repo),
    user_repo: IUserRepository = Depends(get_user_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> dict[str, str]:
    """Revokes the session named by the cookie, if any, and always clears
    the cookie. A missing, expired or already-revoked session is not an
    error here, there is nothing left to revoke, but the browser still
    needs to forget the cookie."""
    require_csrf_header(request)

    token = request.cookies.get(SESSION_COOKIE)
    if token:
        payload = get_token_payload(token, persistent=False)
        if payload and payload.sid:
            try:
                session_id = UUID(payload.sid)
            except ValueError:
                session_id = None
            if session_id is not None:
                session = await session_repo.get_by_public_id(session_id)
                if session is not None and await session_repo.revoke_by_public_id(
                    session.user_id, session.public_id
                ):
                    user = await user_repo.get_by_id(session.user_id)
                    await audit.record(
                        SecurityEventType.LOGOUT,
                        actor=user,
                        target_user=user,
                        target_user_id=session.user_id,
                        target_id=session.id,
                    )
                    await uow.commit()

    clear_session_cookie(response)
    return {"detail": "Logged out"}
