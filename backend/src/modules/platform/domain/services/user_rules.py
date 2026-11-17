"""Pure business rules for user operations. No I/O."""

from typing import Any

from src.modules.platform.const import SYSTEM_USER
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import InvalidSharedAccountMemberError
from src.modules.platform.domain.exceptions import PasswordCriteriaError
from src.modules.platform.domain.exceptions import PasswordNotAllowedError
from src.modules.platform.domain.exceptions import ReservedUsernameError
from src.modules.platform.domain.exceptions import SystemUserProtectedError
from src.modules.platform.domain.exceptions import TerminalPermissionNotAssignableError
from src.modules.platform.domain.exceptions import TimeTrackingCredentialsNotAllowedError
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.auth_provider import AuthProvider
from src.modules.platform.domain.value_objects.permission import Permission

# Fields only an admin acting on *another* user may change. Kept in one place
# because resolve_permission_flags has three separate revert branches, and a
# field added to only some of them is a silent privilege hole.
ADMIN_ONLY_USER_FIELDS = (
    "is_active",
    "permissions",
    "is_shared_account",
    "member_ids",
    "group_ids",
    "auth_provider",
)


def _force_back_admin_only_fields(d: dict[str, Any], target: User) -> dict[str, Any]:
    """Revert every admin-only field to the target's current value."""
    d["is_active"] = target.is_active
    d["permissions"] = list(target.permissions)
    d["is_shared_account"] = target.is_shared_account
    d["member_ids"] = list(target.member_ids)
    d["group_ids"] = list(target.group_ids)
    d["auth_provider"] = target.auth_provider
    return d


class UserRules:
    # ------------------------------------------------------------------
    # Read rules
    # ------------------------------------------------------------------

    @staticmethod
    def assert_can_read_details(actor: User, target_id: int | None = None) -> None:
        """The full user view, with e-mail, permissions, groups, 2FA state and
        the last login, belongs to user administration: read:settings opens
        it, and write:settings too, whose user updates answer with that view
        anyway. Everyone reads their own account. Every other signed-in user
        gets the reduced directory view instead."""
        if target_id is not None and actor.id == target_id:
            return
        if actor.has_permission(Permission.WRITE_SETTINGS):
            return
        assert_has_permission(actor, Permission.READ_SETTINGS, "read", "user details")

    # ------------------------------------------------------------------
    # Creation rules
    # ------------------------------------------------------------------

    @staticmethod
    def assert_can_create(actor: User) -> None:
        """Only users with write:settings (or system) may create new users."""
        assert_has_permission(actor, Permission.WRITE_SETTINGS, "create", "users")

    @staticmethod
    def assert_username_not_reserved(username: str) -> None:
        """`system` is reserved, because that name is exempt from directory
        authentication and always signs in with a local password."""
        if username.strip().lower() == SYSTEM_USER:
            raise ReservedUsernameError(f"The username {SYSTEM_USER!r} is reserved.")

    @staticmethod
    def assert_can_rename(target: User, new_username: str) -> None:
        """The system account cannot be renamed away from its reserved name,
        and no other account may be renamed into it. Either would hand the
        directory bypass to the wrong account."""
        if target.username == SYSTEM_USER and new_username.strip().lower() != SYSTEM_USER:
            raise ReservedUsernameError("The system account cannot be renamed.")
        if target.username != SYSTEM_USER:
            UserRules.assert_username_not_reserved(new_username)

    # ------------------------------------------------------------------
    # Update rules
    # ------------------------------------------------------------------

    @staticmethod
    def assert_can_update(actor: User, target: User) -> None:
        """The system user is only updated by itself; write:settings holders
        update anyone else, and everyone may update themselves."""
        if target.is_systemuser and actor.id != target.id:
            raise SystemUserProtectedError(
                f"User #{actor.id} ({actor.username!r}) tried to update the system user."
            )
        if actor.id != target.id and not actor.has_permission(Permission.WRITE_SETTINGS):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.username!r}) "
                "does not have permission to update other users."
            )

    @staticmethod
    def assert_password_strength(password: str, min_length: int) -> None:
        if len(password) < min_length:
            raise PasswordCriteriaError(
                f"Password does not meet the minimum length of {min_length} characters."
            )

    @staticmethod
    def require_password(password: str | None) -> str:
        """A locally authenticated account needs a password. Returns it
        narrowed to `str`."""
        if not password:
            raise PasswordCriteriaError(
                "A password is required for a locally-authenticated account."
            )
        return password

    @staticmethod
    def assert_password_change_allowed(resulting_auth_provider: str) -> None:
        """Refuses a password for a directory account. It takes the resulting
        provider, so setting a password and switching to LDAP in one request
        is refused too."""
        if resulting_auth_provider == AuthProvider.LDAP:
            raise PasswordNotAllowedError(
                "A directory-authenticated account cannot have a local password. "
                "The directory holds the credential."
            )

    # ------------------------------------------------------------------
    # Permission-flag enforcement
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_permission_flags(actor: User, target: User, data: dict[str, Any]) -> dict[str, Any]:
        """Returns `data` with admin-only fields reverted where the actor may
        not change them: always on the system user, always on oneself (so no
        one can grant themselves operators or leave the directory), and
        whenever the actor lacks write:settings. Reverting is silent because
        PUT /users/me round-trips the full body.

        Unlike PAT and API-key grants, write:settings may grant permissions
        beyond the actor's own. It already allows wholesale user and
        security administration, so a subset cap would not be a real
        boundary.
        """
        d = dict(data)

        # System user's flags are immutable, force them back regardless of
        # actor, and pin it to local auth: `system` is the in-app way back
        # when the directory is misconfigured (see login_policy).
        if target.is_systemuser:
            d = _force_back_admin_only_fields(d, target)
            d["is_active"] = True
            d["auth_provider"] = AuthProvider.LOCAL
            return d

        # Actor cannot change their own permission-level fields.
        if actor.id == target.id:
            return _force_back_admin_only_fields(d, target)

        # Without write:settings the actor cannot change permission fields.
        if not actor.has_permission(Permission.WRITE_SETTINGS):
            return _force_back_admin_only_fields(d, target)

        return d

    @staticmethod
    def assert_permissions_assignable(target: User | None, permissions: list[str]) -> None:
        """The terminal connect permission is held only by the service
        account of a terminal key, which CreateTerminalKey creates. A person
        or another service account never receives it, and a terminal key's
        account keeps exactly that one permission. `target` is None for a
        new user."""
        requested = set(permissions)
        holds = target is not None and Permission.CONNECT_TERMINALS in target.permissions
        if holds and requested != {Permission.CONNECT_TERMINALS}:
            raise TerminalPermissionNotAssignableError(
                "The account of a terminal key keeps exactly its terminal permission."
            )
        if not holds and Permission.CONNECT_TERMINALS in requested:
            raise TerminalPermissionNotAssignableError(
                f"{Permission.CONNECT_TERMINALS} is held only by terminal keys."
            )

    # ------------------------------------------------------------------
    # Shared-account membership rules
    # ------------------------------------------------------------------

    @staticmethod
    def assert_valid_shared_account_member(target_id: int | None, candidate: User | None) -> None:
        """Members of a shared account must be active personal users, never
        the account itself, a service account or another shared account."""
        if candidate is None:
            raise InvalidSharedAccountMemberError("Referenced member user does not exist.")
        if candidate.id == target_id:
            raise InvalidSharedAccountMemberError(
                "A shared account cannot list itself as a member."
            )
        if not candidate.is_active:
            raise InvalidSharedAccountMemberError(
                f"User #{candidate.id} ({candidate.username!r}) is not active."
            )
        if candidate.is_service_account:
            raise InvalidSharedAccountMemberError(
                f"User #{candidate.id} ({candidate.username!r}) is a service account "
                "and cannot be an operator."
            )
        if candidate.is_shared_account:
            raise InvalidSharedAccountMemberError(
                f"User #{candidate.id} ({candidate.username!r}) is itself a shared account "
                "and cannot be an operator."
            )

    # ------------------------------------------------------------------
    # Time tracking credentials
    # ------------------------------------------------------------------

    @staticmethod
    def is_personal_account(user: User) -> bool:
        """Neither a shared, a service nor the system account."""
        return not (user.is_shared_account or user.is_service_account or user.is_systemuser)

    @staticmethod
    def assert_time_tracking_credentials_allowed(user: User, *, has_credentials: bool) -> None:
        """Time tracking credentials belong to one person, so only personal
        accounts may hold them. `has_credentials` says whether the account
        holds or is about to hold any; without them nothing is checked, so
        create flows can call this for every new account."""
        if not has_credentials or UserRules.is_personal_account(user):
            return
        raise TimeTrackingCredentialsNotAllowedError(
            "Only personal accounts can hold time tracking credentials, shared, service and "
            "system accounts cannot. Remove the account's time tracking credentials before "
            "turning it into a shared or service account."
        )

    @staticmethod
    def assert_can_delete_time_tracking_credentials(actor: User, target_id: int) -> None:
        """Removing another user's time tracking credentials is user
        administration and needs write:settings; one's own never does. Takes
        the target's id, so the check runs before the user is loaded."""
        if actor.id == target_id:
            return
        assert_has_permission(
            actor, Permission.WRITE_SETTINGS, "delete", "another user's time tracking credentials"
        )

    # ------------------------------------------------------------------
    # Force-logout rules
    # ------------------------------------------------------------------

    @staticmethod
    def assert_can_force_logout(actor: User, target: User) -> None:
        """The system user cannot be force-logged out; others' sessions need
        write:settings, one's own never do."""
        if target.is_systemuser:
            raise SystemUserProtectedError(
                f"User #{actor.id} ({actor.username!r}) tried to force-logout the system user."
            )
        if actor.id == target.id:
            return
        assert_has_permission(actor, Permission.WRITE_SETTINGS, "logout", "users")

    @staticmethod
    def assert_can_reset_totp(actor: User, target: User) -> None:
        """Resetting another user's 2FA needs write:settings. Nobody resets
        their own here, because the self-service route demands the current
        code and a hijacked session must not skip it. The system user's 2FA
        is never reset."""
        if target.is_systemuser:
            raise SystemUserProtectedError(
                f"User #{actor.id} ({actor.username!r}) tried to reset the system user's 2FA."
            )
        if actor.id == target.id:
            raise InsufficientPermissionsError(
                "Use the confirmed self-service route to remove your own 2FA."
            )
        assert_has_permission(actor, Permission.WRITE_SETTINGS, "reset", "another user's 2FA")

    @staticmethod
    def assert_can_disable_totp(user: User) -> None:
        """The system user's 2FA is mandatory. Only the `admin reset-totp`
        CLI clears it, and that forces immediate re-enrolment."""
        if user.is_systemuser:
            raise SystemUserProtectedError(
                "2FA cannot be disabled for the system account. Use `admin "
                "reset-totp system` instead, which forces re-enrolment on the "
                "next login."
            )

    @staticmethod
    def assert_can_register_passkey(user: User) -> None:
        """A passkey skips the TOTP step, so the system user, whose 2FA is
        mandatory, never holds one. Service accounts never sign in
        interactively at all."""
        if user.is_systemuser:
            raise SystemUserProtectedError("The system account cannot use passkeys.")
        if user.is_service_account:
            raise InsufficientPermissionsError("Service accounts cannot use passkeys.")

    @staticmethod
    def assert_can_reset_passkeys(actor: User, target_id: int) -> None:
        """Removing another user's passkeys needs write:settings, the way back
        for a lost or stolen device. Your own go through the self-service
        routes instead. It takes only the target's id, so it runs before the
        target is fetched and a caller without the permission cannot tell an
        existing user from a missing one."""
        if actor.id == target_id:
            raise InsufficientPermissionsError(
                "Use the self-service route to remove your own passkeys."
            )
        assert_has_permission(actor, Permission.WRITE_SETTINGS, "reset", "another user's passkeys")

    # ------------------------------------------------------------------
    # Deletion rules
    # ------------------------------------------------------------------

    @staticmethod
    def assert_can_delete(actor: User, target: User) -> None:
        """Deleting needs write:settings, never targets oneself and never
        the system user."""
        if target.is_systemuser:
            raise SystemUserProtectedError(
                f"User #{actor.id} ({actor.username!r}) tried to delete the system user."
            )
        if actor.id == target.id:
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.username!r}) cannot delete their own account."
            )
        assert_has_permission(actor, Permission.WRITE_SETTINGS, "delete", "users")
