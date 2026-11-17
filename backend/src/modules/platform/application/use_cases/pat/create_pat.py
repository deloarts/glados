"""
Generates a new personal access token for the acting user. Unlike an API
key, a PAT does not create a backing User row, it authenticates as the
same user who created it, so the token row and its security log entry are
the only writes the unit of work commits.

The web route goes through CreatePatWithPassword, which asks for the
password again even though the caller has a session: a token outlives the
session and is not ended by signing out, so whoever finds an unlocked
session must not be able to turn it into lasting access. Wrong passwords
count toward the login throttle (password_confirmation.py).
"""

from datetime import timedelta

from src.modules.platform.application.dto.pat_dto import CreatedPatResult
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.mappers.pat_mapper import PatMapper
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.services.token_lifetime_cap import read_token_lifetime_cap_for
from src.modules.platform.application.use_cases.user.password_confirmation import (
    PasswordConfirmation,
)
from src.modules.platform.domain.entities.personal_access_token import PersonalAccessToken
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.pat_rules import PatRules
from src.modules.platform.domain.services.token_lifetime import assert_lifetime_days_allowed
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.security.pat import display_prefix
from src.modules.platform.infrastructure.security.pat import generate_pat
from src.modules.platform.infrastructure.security.pat import hash_pat
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class CreatePat:
    def __init__(
        self,
        pat_repo: IPatRepository,
        settings_repo: IPlatformSettingsRepository,
        *,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._pats = pat_repo
        self._settings = settings_repo
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, actor: User, cmd: CreatePatCommand) -> CreatedPatResult:
        PatRules.assert_can_create(actor)
        PatRules.assert_permissions_allowed(cmd.permissions, actor)

        cap = await read_token_lifetime_cap_for(
            cmd.permissions, self._settings.get_security, lambda: self._settings.get_agents()
        )
        assert_lifetime_days_allowed(cmd.expires_in_days, cap)

        raw_token = generate_pat()
        now = now_utc()

        token = PersonalAccessToken(
            id=0,
            name=cmd.name,
            token_hash=hash_pat(raw_token),
            token_prefix=display_prefix(raw_token),
            user_id=actor.id,
            permissions=list(cmd.permissions),
            created=now,
            expires_at=now + timedelta(days=cmd.expires_in_days)
            if cmd.expires_in_days is not None
            else None,
            revoked_at=None,
        )
        saved = await self._pats.save(token)
        await self._audit.record(
            SecurityEventType.PAT_CREATED,
            actor=actor,
            target_user=actor,
            target_id=saved.id,
            detail={
                "name": saved.name,
                "permissions": saved.permissions,
                "expires_at": saved.expires_at.isoformat() if saved.expires_at else None,
            },
        )
        await self._uow.commit()

        log.info(
            "Created personal access token %r (ID=%s).",
            saved.name,
            saved.id,
        )
        return PatMapper.to_created_result(saved, raw_token)


class CreatePatWithPassword:
    """CreatePat behind a confirmation of the acting user's own password, the
    way the self-service route creates a token."""

    def __init__(self, create_pat: CreatePat, password_confirmation: PasswordConfirmation) -> None:
        self._create_pat = create_pat
        self._password_confirmation = password_confirmation

    async def execute(
        self, actor: User, cmd: CreatePatCommand, *, password: str, client_ip: str | None = None
    ) -> CreatedPatResult:
        # The account rules come first, so a caller who may not create the
        # token anyway does not spend a password attempt on finding out.
        PatRules.assert_can_create(actor)
        PatRules.assert_permissions_allowed(cmd.permissions, actor)
        confirmed = await self._password_confirmation.confirm(actor, password, client_ip=client_ip)
        return await self._create_pat.execute(actor=confirmed, cmd=cmd)
