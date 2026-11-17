"""
Pure business rules for product operations. No I/O.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.services.designated_user_rules import (
    assert_can_assign_designated_user as _assert_can_assign_designated_user,
)
from src.modules.platform.domain.services.designated_user_rules import (
    resolve_designated_user as _resolve_designated_user,
)
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.entities.product import Product


class ProductRules:
    # ── Create ────────────────────────────────────────────────────────

    @staticmethod
    def assert_can_create(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_PROJECTS, "create", "products")

    @staticmethod
    def resolve_designated_user(actor: User, designated_user_id: int | None) -> int:
        """Create-time resolution, see designated_user_rules.py."""
        return _resolve_designated_user(actor, designated_user_id)

    @staticmethod
    def assert_can_assign_designated_user(actor: User, designated_user_id: int) -> None:
        """Update-time counterpart: rejects instead of silently
        rewriting. See designated_user_rules.py."""
        _assert_can_assign_designated_user(actor, designated_user_id, "products")

    # ── Update ────────────────────────────────────────────────────────

    @staticmethod
    def assert_can_update(actor: User, product: Product) -> None:
        if (
            not actor.has_permission(Permission.MANAGE_PROJECTS)
            and actor.id != product.designated_user_id
        ):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.username!r}) cannot update "
                f"product #{product.id} ({product.product_number!r}): insufficient permissions."
            )

    # ── Archive / restore ────────────────────────────────────────────────

    @staticmethod
    def assert_can_archive(actor: User) -> None:
        assert_has_permission(actor, Permission.MANAGE_PROJECTS, "archive", "products")

    @staticmethod
    def assert_can_restore(actor: User) -> None:
        assert_has_permission(actor, Permission.MANAGE_PROJECTS, "restore", "products")
