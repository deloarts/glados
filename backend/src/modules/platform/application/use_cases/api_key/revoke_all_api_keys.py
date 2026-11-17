"""
Admin bulk revoke, every currently-active key, regardless of who created
it (API keys are an admin-managed resource, unlike PATs which are scoped
to their own owner). Each backing service-account User is deactivated in
the same transaction, same as a single RevokeApiKey, and each revocation is
recorded in the security log.
"""

from src.modules.platform.application.services.api_key_issuing import api_key_event
from src.modules.platform.application.services.paging import fetch_all
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.api_key_rules import ApiKeyRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.api_key_repository import ApiKeyFilterDto
from src.modules.platform.ports.outbound.repositories.api_key_repository import IApiKeyRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class RevokeAllApiKeys:
    def __init__(
        self,
        key_repo: IApiKeyRepository,
        user_repo: IUserRepository,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._keys = key_repo
        self._users = user_repo
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, actor: User) -> int:
        ApiKeyRules.assert_can_manage(actor)

        keys = await fetch_all(
            lambda skip, limit: self._keys.get_multi(ApiKeyFilterDto(skip=skip, limit=limit)),
            MAX_PAGE_SIZE,
        )
        now = now_utc()

        count = 0
        for key in keys:
            key.revoked_at = now
            await self._keys.save(key)

            service_user = await self._users.get_by_id(key.user_id)
            if service_user is not None:
                service_user.is_active = False
                await self._users.save(service_user)

            await self._audit.record(
                api_key_event(key, created=False),
                actor=actor,
                target_user=service_user,
                target_user_id=key.user_id,
                target_id=key.id,
                detail={"name": key.name, "scope": "all"},
            )
            count += 1

        await self._uow.commit()
        log.info("Revoked all (%s) API keys.", count)
        return count
