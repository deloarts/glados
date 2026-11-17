"""
Orchestrates user updates: enforces permissions, re-checks username, email, and rfid uniqueness,
validates and hashes a new password alongside the auth_provider transitions that invalidate or
require one, indexes rfid values, and resolves role flags.

A user changing their own password must give the current one, checked through the login throttle
(password_confirmation.py), so a session left open cannot be turned into a changed password. An
administrator setting someone else's password is not asked for it. A changed password ends the
account's other sessions and revokes its trusted devices and personal access tokens, so changing
it recovers an account whose password was known to someone else.

Time tracking credentials belong to a person: turning an account that holds them into a shared or
service account is refused until they are removed, and deactivating an account deletes them.

Group memberships follow the permissions: only a write:settings holder changes them, never on
their own account, and a change that adds or removes a group tells the user their permissions
changed.

A changed password, deactivation, reactivation, change of direct permissions and change of
group memberships are each recorded in the security log, in the transaction of the update.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any

from src.modules.platform.application.dto.user_dto import UpdateUserCommand
from src.modules.platform.application.dto.user_dto import UserResult
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.services.user_group_membership import validated_group_ids
from src.modules.platform.application.use_cases.user.password_confirmation import (
    PasswordConfirmation,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.events.user_events import UserDeactivated
from src.modules.platform.domain.events.user_events import UserPermissionsChanged
from src.modules.platform.domain.exceptions import CurrentPasswordRequiredError
from src.modules.platform.domain.exceptions import EmailAlreadyExistsError
from src.modules.platform.domain.exceptions import PasswordCriteriaError
from src.modules.platform.domain.exceptions import RfidAlreadyExistsError
from src.modules.platform.domain.exceptions import UsernameAlreadyExistsError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.user_rules import UserRules
from src.modules.platform.domain.value_objects.auth_provider import AuthProvider
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.logging.context import current_session_id
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.security.hashing import is_unusable_hash
from src.modules.platform.infrastructure.security.hashing import unusable_password_hash
from src.modules.platform.infrastructure.security.rfid import rfid_lookup
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.repositories.pat_repository import IPatRepository
from src.modules.platform.ports.outbound.repositories.trusted_device_repository import (
    ITrustedDeviceRepository,
)
from src.modules.platform.ports.outbound.repositories.user_group_repository import (
    IUserGroupRepository,
)
from src.modules.platform.ports.outbound.repositories.user_pdm_link_repository import (
    IUserPdmLinkRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.platform.ports.outbound.user_held_credentials_port import IUserHeldCredentials


class UpdateUser:
    def __init__(
        self,
        user_repo: IUserRepository,
        min_password_length: int,
        hash_fn: Callable[[str], Awaitable[str]],
        session_repo: IUserSessionRepository,
        trusted_device_repo: ITrustedDeviceRepository,
        link_repo: IUserPdmLinkRepository,
        *,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        time_tracking_credentials_repo: IUserHeldCredentials | None = None,
        group_repo: IUserGroupRepository | None = None,
        pat_repo: IPatRepository | None = None,
        password_confirmation: PasswordConfirmation | None = None,
        audit: SecurityAudit | None = None,
    ) -> None:
        self._repo = user_repo
        self._min_pw_len = min_password_length
        self._hash = hash_fn
        self._sessions = session_repo
        self._trusted_devices = trusted_device_repo
        self._links = link_repo
        self._bus = event_bus
        self._uow = uow
        self._time_tracking_credentials = time_tracking_credentials_repo
        self._groups = group_repo
        self._pats = pat_repo
        self._password_confirmation = password_confirmation
        self._audit = audit or SecurityAudit.disabled()

    async def execute(
        self,
        actor: User,
        target_id: int,
        cmd: UpdateUserCommand,
        *,
        client_ip: str | None = None,
    ) -> UserResult:
        # Load target
        target = found_or_raise(
            await self._repo.get_by_id(target_id),
            UserNotFoundError,
            f"User #{target_id} not found.",
        )

        # Permission checks
        UserRules.assert_can_update(actor, target)

        # Before anything else is judged or changed, since proving the
        # password re-reads the account and ends the read transaction.
        if actor.id == target.id and cmd.password:
            await self._confirm_own_password(actor, target, cmd.current_password, client_ip)

        # Build update dict from only the provided fields
        data = cmd.model_dump(exclude_unset=True)
        data.pop("current_password", None)

        await self._assert_username_available(target, data)
        await self._assert_email_available(target, data)
        await self._apply_rfid(target, data)

        # permissions/member_ids=None means "don't change", omit rather than set null
        if data.get("permissions") is None:
            data.pop("permissions", None)
        if data.get("member_ids") is None:
            data.pop("member_ids", None)
        if data.get("group_ids") is None:
            data.pop("group_ids", None)

        # Permission-flag resolution (who can change what)
        data = UserRules.resolve_permission_flags(actor, target, data)
        if "permissions" in data:
            UserRules.assert_permissions_assignable(target, list(data["permissions"]))

        password_changed = await self._resolve_password(data, target)
        await self._resolve_shared_account_members(data, target)

        # Apply changes to entity
        groups_before = list(target.group_ids)
        permissions_before = list(target.permissions)
        was_active = target.is_active
        for key, value in data.items():
            if hasattr(target, key):
                setattr(target, key, value)
        if "group_ids" in data:
            target.group_ids = await validated_group_ids(
                self._groups, target, list(data["group_ids"])
            )

        await self._assert_time_tracking_credentials_allowed(target)
        saved = await self._repo.save(target)
        if data.get("is_active") is False and self._time_tracking_credentials is not None:
            await self._time_tracking_credentials.delete_for_user(saved.id)

        if password_changed:
            await self._revoke_credentials_after_password_change(actor, target)

        await self._record_security_events(
            actor,
            saved,
            password_changed=password_changed,
            was_active=was_active,
            permissions_before=permissions_before,
            groups_before=groups_before,
        )

        if "permissions" in data or saved.group_ids != groups_before:
            await self._bus.publish(UserPermissionsChanged(user_id=saved.id, actor_id=actor.id))
        if data.get("is_active") is False:
            await self._bus.publish(UserDeactivated(user_id=saved.id, actor_id=actor.id))
        await self._uow.commit()

        log.info(f"Updated user {target.username!r} (ID={target.id}).")

        return UserMapper.to_result(saved, await self._links.list_by_user(saved.id))

    async def _record_security_events(
        self,
        actor: User,
        saved: User,
        *,
        password_changed: bool,
        was_active: bool,
        permissions_before: list[str],
        groups_before: list[int],
    ) -> None:
        """One security log entry per kind of change the update made."""
        if password_changed:
            await self._audit.record(
                SecurityEventType.PASSWORD_CHANGED,
                actor=actor,
                target_user=saved,
                detail={"by_self": actor.id == saved.id, "auth_provider": saved.auth_provider},
            )
        if was_active and not saved.is_active:
            await self._audit.record(
                SecurityEventType.USER_DEACTIVATED, actor=actor, target_user=saved
            )
        elif not was_active and saved.is_active:
            await self._audit.record(
                SecurityEventType.USER_REACTIVATED, actor=actor, target_user=saved
            )
        permissions_changed = _difference(permissions_before, saved.permissions)
        if permissions_changed:
            await self._audit.record(
                SecurityEventType.USER_PERMISSIONS_CHANGED,
                actor=actor,
                target_user=saved,
                detail=permissions_changed,
            )
        groups_changed = _difference(groups_before, saved.group_ids)
        if groups_changed:
            await self._audit.record(
                SecurityEventType.USER_GROUPS_CHANGED,
                actor=actor,
                target_user=saved,
                detail=groups_changed,
            )

    async def _assert_time_tracking_credentials_allowed(self, target: User) -> None:
        """Runs on the resolved target, so it sees the shared and service
        flags as they would be saved."""
        if self._time_tracking_credentials is None or UserRules.is_personal_account(target):
            return
        UserRules.assert_time_tracking_credentials_allowed(
            target,
            has_credentials=await self._time_tracking_credentials.exists_for_user(target.id),
        )

    async def _assert_username_available(self, target: User, data: dict[str, Any]) -> None:
        if "username" not in data:
            return
        UserRules.assert_can_rename(target, data["username"])
        existing = await self._repo.get_by_username(data["username"])
        if existing and existing.id != target.id:
            raise UsernameAlreadyExistsError(f"Username {data['username']!r} is already taken.")

    async def _assert_email_available(self, target: User, data: dict[str, Any]) -> None:
        if "email" not in data:
            return
        existing = await self._repo.get_by_email(data["email"])
        if existing and existing.id != target.id:
            raise EmailAlreadyExistsError(f"Email {data['email']!r} is already taken.")

    async def _apply_rfid(self, target: User, data: dict[str, Any]) -> None:
        if "rfid" not in data:
            return
        rfid = data.pop("rfid")
        if rfid is not None:
            existing = await self._repo.get_by_rfid(rfid)
            if existing and existing.id != target.id:
                raise RfidAlreadyExistsError(
                    "The given RFID is already assigned to another account."
                )
            data["rfid_lookup"] = rfid_lookup(rfid)
        else:
            data["rfid_lookup"] = None

    async def _resolve_password(self, data: dict[str, Any], target: User) -> bool:
        """Deliberately called *after* resolve_permission_flags, because
        that call decides the resulting auth_provider, silently reverting
        it for a self-update. Checking beforehand would let a directory
        user send {password, auth_provider: "local"} and walk away with a
        working local password on an account whose provider was reverted
        to ldap. Returns whether the stored password hash changed, for the
        caller's post-save session/device revocation."""
        resulting_provider = data.get("auth_provider", target.auth_provider)
        provider_changed = resulting_provider != target.auth_provider
        password_changed = False

        if "password" in data:
            if not data["password"]:
                del data["password"]
            else:
                UserRules.assert_password_change_allowed(resulting_provider)
                UserRules.assert_password_strength(data["password"], self._min_pw_len)
                data["hashed_password"] = await self._hash(data.pop("password"))
                password_changed = True

        if provider_changed and resulting_provider == AuthProvider.LDAP:
            # Moving onto the directory: the local password stops working now,
            # not whenever this row happens to be touched next.
            data["hashed_password"] = unusable_password_hash()
            password_changed = True
        elif provider_changed and is_unusable_hash(target.hashed_password) and not password_changed:
            # Coming back off the directory. The stored hash is still the
            # sentinel, so without a password in this same request the save
            # would produce an account nobody can ever sign in to.
            raise PasswordCriteriaError(
                "Moving this account off the directory requires a password: "
                "it has no local one to fall back on."
            )

        return password_changed

    async def _confirm_own_password(
        self, actor: User, target: User, current_password: str | None, client_ip: str | None
    ) -> None:
        """Proves the actor's current password before they set a new one.
        A directory account is refused outright, as _resolve_password would
        refuse it, rather than being asked for a password it cannot change."""
        UserRules.assert_password_change_allowed(target.auth_provider)
        if not current_password:
            raise CurrentPasswordRequiredError(
                "Changing your own password requires your current password."
            )
        if self._password_confirmation is None:
            raise RuntimeError("UpdateUser needs a PasswordConfirmation for own password changes.")
        await self._password_confirmation.confirm(actor, current_password, client_ip=client_ip)

    async def _resolve_shared_account_members(self, data: dict[str, Any], target: User) -> None:
        """Forced empty once is_shared_account resolves false, otherwise
        every referenced id must be a valid operator candidate."""
        resulting_is_shared_account = data.get("is_shared_account", target.is_shared_account)
        if not resulting_is_shared_account:
            if target.member_ids or data.get("member_ids"):
                data["member_ids"] = []
        elif "member_ids" in data:
            validated_member_ids: list[int] = []
            for member_id in data["member_ids"]:
                candidate = await self._repo.get_by_id(member_id)
                UserRules.assert_valid_shared_account_member(
                    target_id=target.id, candidate=candidate
                )
                validated_member_ids.append(member_id)
            data["member_ids"] = validated_member_ids

    async def _revoke_credentials_after_password_change(self, actor: User, target: User) -> None:
        """A changed password ends every other session, un-trusts every
        device and revokes every personal access token, since any of them
        may have been obtained with the old password. When the user changed
        it themselves, the session that made the change survives (via
        current_session_id); an admin changing someone else's password
        revokes all of the target's sessions, the admin's own session
        belongs to a different account and is not at stake."""
        keep = current_session_id() if actor.id == target.id else None
        revoked = await self._sessions.revoke_all_for_user_except(target.id, keep)
        await self._trusted_devices.revoke_all_for_user(target.id)
        revoked_pats = await self._pats.revoke_all_for_user(target.id) if self._pats else 0
        if revoked_pats:
            await self._audit.record(
                SecurityEventType.PAT_REVOKED,
                actor=actor,
                target_user=target,
                detail={"scope": "all", "count": revoked_pats, "reason": "password_changed"},
            )
        log.info(
            f"Password change for user ID={target.id}: revoked {revoked} other "
            f"session(s), {revoked_pats} personal access token(s) and all trusted devices."
        )


def _difference[T: (str, int)](before: list[T], after: list[T]) -> dict[str, list[T]]:
    """What `after` added to and removed from `before`, empty when nothing
    changed."""
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    if not added and not removed:
        return {}
    return {"added": added, "removed": removed}
