"""
Revokes a single personal access token by setting revoked_at, enforcing management
permissions, and records the revocation in the security log.
"""

from src.modules.platform.application.dto.pat_dto import PatResult
from src.modules.platform.application.mappers.pat_mapper import PatMapper
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import PatNotFoundError
from src.modules.platform.domain.services.pat_rules import PatRules
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class RevokePat:
    def __init__(
        self, pat_repo: IPatRepository, *, uow: IUnitOfWork, audit: SecurityAudit | None = None
    ) -> None:
        self._pats = pat_repo
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, actor: User, pat_id: int) -> PatResult:
        token = found_or_raise(
            await self._pats.get_by_id(pat_id),
            PatNotFoundError,
            f"Personal access token #{pat_id} not found.",
        )
        PatRules.assert_can_manage(actor, token)

        if token.revoked_at is None:
            token.revoked_at = now_utc()
            token = await self._pats.save(token)
            await self._audit.record(
                SecurityEventType.PAT_REVOKED,
                actor=actor,
                target_user=actor if actor.id == token.user_id else None,
                target_user_id=token.user_id,
                target_id=token.id,
                detail={"name": token.name},
            )
            await self._uow.commit()
            log.info(
                "Revoked personal access token %r (ID=%s).",
                token.name,
                pat_id,
            )

        return PatMapper.to_result(token)
