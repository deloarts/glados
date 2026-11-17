"""
Business rules for the source item domain. No I/O. No ORM. No config imports.
"""

from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.errors import SourceItemInactiveError
from src.modules.catalogue.domain.policies.catalogue_item_status import demandable_refusal
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission


class SourceItemCatalogueRules:
    @staticmethod
    def assert_can_create(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_SOURCE_ITEMS, "create", "source items")

    @staticmethod
    def assert_can_update(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_SOURCE_ITEMS, "update", "source items")

    @staticmethod
    def assert_can_archive(actor: User) -> None:
        assert_has_permission(actor, Permission.DELETE_SOURCE_ITEMS, "archive", "source items")

    @staticmethod
    def assert_can_restore(actor: User) -> None:
        assert_has_permission(actor, Permission.DELETE_SOURCE_ITEMS, "restore", "source items")

    @staticmethod
    def assert_item_active(item: SourceItem) -> None:
        if item.status != SourceItemCatalogueStatus.ACTIVE.value:
            raise SourceItemInactiveError(
                f"Source item #{item.id} is not active (status={item.status.value})."
            )

    @staticmethod
    def assert_item_demandable(item: SourceItem) -> None:
        """Refuses a new demand or order line for an item that is not active
        or is archived. Source items have no PDM file."""
        reason = demandable_refusal(status=item.status, archived=item.archived)
        if reason is not None:
            raise SourceItemInactiveError(
                f"Source item #{item.id} {reason}, so no new demand or order line can name it."
            )
