"""
Business rules for the API key domain. No I/O. No ORM.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import ExcessiveApiKeyPermissionsError
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.services.token_permission_rules import (
    assert_requested_permissions_allowed,
)
from src.modules.platform.domain.value_objects.permission import Permission


class ApiKeyRules:
    @staticmethod
    def assert_can_manage(actor: User) -> None:
        assert_has_permission(actor, Permission.MANAGE_API_KEYS, "manage", "API keys")

    @staticmethod
    def assert_permissions_allowed(requested: list[str], actor: User) -> None:
        assert_requested_permissions_allowed(
            requested,
            actor,
            exception_class=ExcessiveApiKeyPermissionsError,
            noun="API keys",
        )
