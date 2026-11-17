"""
Listing and removing passkeys: the acting user's own, and, for holders of
write:settings, another user's, which is the way back for a lost or stolen
device. Removing a passkey does not end sessions it already signed in;
force-logout is its own action, as for the administrative 2FA reset.
Every removal is recorded in the security log.
"""

from uuid import UUID

from src.modules.platform.application.dto.passkey_dto import PasskeyResult
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.domain.entities.passkey import Passkey
from src.modules.platform.domain.entities.passkey import passkey_name
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import PasskeyNotFoundError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.user_rules import UserRules
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.repositories.passkey_repository import IPasskeyRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def to_passkey_result(passkey: Passkey) -> PasskeyResult:
    return PasskeyResult(
        id=passkey.id,
        public_id=passkey.public_id,
        name=passkey.name,
        created_at=passkey.created_at,
        last_used_at=passkey.last_used_at,
        backed_up=passkey.backed_up,
    )


class GetMyPasskeys:
    def __init__(self, passkey_repo: IPasskeyRepository) -> None:
        self._passkeys = passkey_repo

    async def execute(self, actor: User) -> list[PasskeyResult]:
        return [to_passkey_result(p) for p in await self._passkeys.list_for_user(actor.id)]


class RenameMyPasskey:
    def __init__(self, passkey_repo: IPasskeyRepository, *, uow: IUnitOfWork) -> None:
        self._passkeys = passkey_repo
        self._uow = uow

    async def execute(self, actor: User, public_id: UUID, name: str) -> PasskeyResult:
        """Scoped by actor.id like DeleteMyPasskey. A blank name is refused
        by the schema, so the stored name is never empty."""
        passkey = found_or_raise(
            await self._passkeys.get_for_user(actor.id, public_id),
            PasskeyNotFoundError,
            f"Passkey {public_id} not found.",
        )
        passkey.name = passkey_name(name)
        saved = await self._passkeys.save(passkey)
        await self._uow.commit()
        log.info(f"Renamed passkey {public_id} to {saved.name!r}.")
        return to_passkey_result(saved)


class DeleteMyPasskey:
    def __init__(
        self,
        passkey_repo: IPasskeyRepository,
        *,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._passkeys = passkey_repo
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, actor: User, public_id: UUID) -> None:
        """Scoped by actor.id in the repository call, a guessed public_id
        belonging to someone else 404s exactly like a nonexistent one."""
        if not await self._passkeys.delete_by_public_id(actor.id, public_id):
            raise PasskeyNotFoundError(f"Passkey {public_id} not found.")
        await self._audit.record(
            SecurityEventType.PASSKEY_REMOVED,
            actor=actor,
            target_user=actor,
            detail={"passkey": str(public_id), "count": 1},
        )
        await self._uow.commit()
        log.info(f"Removed passkey {public_id}.")


class DeleteAllMyPasskeys:
    def __init__(
        self,
        passkey_repo: IPasskeyRepository,
        *,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._passkeys = passkey_repo
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, actor: User) -> int:
        count = await self._passkeys.delete_all_for_user(actor.id)
        if count:
            await self._audit.record(
                SecurityEventType.PASSKEY_REMOVED,
                actor=actor,
                target_user=actor,
                detail={"scope": "all", "count": count},
            )
        await self._uow.commit()
        log.info(f"Removed all {count} own passkey(s).")
        return count


class GetUserPasskeys:
    def __init__(self, user_repo: IUserRepository, passkey_repo: IPasskeyRepository) -> None:
        self._users = user_repo
        self._passkeys = passkey_repo

    async def execute(self, actor: User, target_id: int) -> list[PasskeyResult]:
        """Another user's passkeys, under the same rule as removing them."""
        UserRules.assert_can_reset_passkeys(actor, target_id)
        target = found_or_raise(
            await self._users.get_by_id(target_id),
            UserNotFoundError,
            f"User #{target_id} not found.",
        )
        return [to_passkey_result(p) for p in await self._passkeys.list_for_user(target.id)]


class ResetUserPasskeys:
    def __init__(
        self,
        user_repo: IUserRepository,
        passkey_repo: IPasskeyRepository,
        *,
        uow: IUnitOfWork,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._users = user_repo
        self._passkeys = passkey_repo
        self._uow = uow
        self._audit = audit or SecurityAudit.disabled()

    async def execute(self, actor: User, target_id: int) -> int:
        UserRules.assert_can_reset_passkeys(actor, target_id)
        target = found_or_raise(
            await self._users.get_by_id(target_id),
            UserNotFoundError,
            f"User #{target_id} not found.",
        )
        count = await self._passkeys.delete_all_for_user(target.id)
        if count:
            await self._audit.record(
                SecurityEventType.PASSKEY_REMOVED,
                actor=actor,
                target_user=target,
                detail={"scope": "all", "count": count},
            )
        await self._uow.commit()
        # Security-relevant administrative action: record who did it and to
        # whom, not just that it happened.
        log.info(f"Removed {count} passkey(s) of {target.username!r} (ID={target.id}).")
        return count
