"""
Self-service bulk revoke, always scoped to the acting user's own tokens.
There is no admin variant; an admin revoking another user's tokens still
goes through RevokePat (or force-logout, which revokes as a side effect).
One security log entry records the whole revocation.
"""

from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class RevokeAllPats:
    def __init__(
        self, pat_repo: IPatRepository, *, uow: IUnitOfWork, audit: SecurityAudit | None = None
    ) -> None:
        self._pats = pat_repo
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, actor: User) -> int:
        count = await self._pats.revoke_all_for_user(actor.id)
        if count:
            await self._audit.record(
                SecurityEventType.PAT_REVOKED,
                actor=actor,
                target_user=actor,
                detail={"scope": "all", "count": count},
            )
        await self._uow.commit()
        log.info("Revoked all (%s) personal access tokens.", count)
        return count
