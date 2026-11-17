"""
Business rules for the personal access token (PAT) domain. No I/O. No ORM.
"""

from src.modules.platform.domain.entities.personal_access_token import PersonalAccessToken
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import ExcessivePatPermissionsError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.services.token_permission_rules import (
    assert_requested_permissions_allowed,
)
from src.modules.platform.domain.value_objects.permission import Permission


class PatRules:
    @staticmethod
    def assert_can_create(actor: User) -> None:
        # Checked before the permission below: User.has_permission returns
        # True for every permission when is_systemuser, so testing that
        # first would let the break-glass account mint a token carrying
        # its own unrestricted access, exactly the "cannot create PATs"
        # rule this is meant to close.
        if actor.is_systemuser:
            raise InsufficientPermissionsError(
                "The system account cannot create personal access tokens."
            )
        assert_has_permission(actor, Permission.WRITE_PAT, "create", "a PAT")

    @staticmethod
    def assert_can_manage(actor: User, token: PersonalAccessToken) -> None:
        """A user may always manage (view/revoke) their own tokens.
        Managing another user's token requires write:settings."""
        if actor.id == token.user_id:
            return
        assert_has_permission(
            actor, Permission.WRITE_SETTINGS, "manage", "this personal access token"
        )

    @staticmethod
    def assert_permissions_allowed(requested: list[str], actor: User) -> None:
        assert_requested_permissions_allowed(
            requested,
            actor,
            exception_class=ExcessivePatPermissionsError,
            noun="Personal access tokens",
        )
