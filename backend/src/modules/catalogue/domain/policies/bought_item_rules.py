"""
Business rules for the bought item domain, one class per aggregate.
No I/O. No ORM. No config imports.
"""

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.errors import BoughtItemInactiveError
from src.modules.catalogue.domain.policies.catalogue_item_status import MergeTargetRefusal
from src.modules.catalogue.domain.policies.catalogue_item_status import demandable_refusal
from src.modules.catalogue.domain.policies.catalogue_item_status import merge_target_verdict
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission

# ── Catalogue item rules ──────────────────────────────────────────────


class BoughtItemCatalogueRules:
    @staticmethod
    def assert_can_create(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_BOUGHT_ITEMS, "create", "catalogue items")

    @staticmethod
    def assert_can_update(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_BOUGHT_ITEMS, "update", "catalogue items")

    @staticmethod
    def assert_can_archive(actor: User) -> None:
        assert_has_permission(actor, Permission.DELETE_BOUGHT_ITEMS, "archive", "catalogue items")

    @staticmethod
    def assert_can_restore(actor: User) -> None:
        assert_has_permission(actor, Permission.DELETE_BOUGHT_ITEMS, "restore", "catalogue items")

    @staticmethod
    def assert_item_active(item: BoughtItem) -> None:
        if item.status != BoughtItemCatalogueStatus.ACTIVE.value:
            raise BoughtItemInactiveError(
                f"Catalogue item #{item.id} ({item.article_name}) is not active "
                f"(status={item.status.value})."
            )

    @staticmethod
    def assert_merge_target(target: BoughtItem, source: BoughtItem) -> bool:
        """Refuses a target that may not take the merge of the source (see
        merge_target_verdict), and returns True when the merge makes the
        target active again."""
        verdict = merge_target_verdict(
            archived=target.archived,
            status=target.status,
            successor_item_id=target.successor_item_id,
            source_id=source.id,
        )
        if verdict.refusal is MergeTargetRefusal.ARCHIVED:
            raise BoughtItemInactiveError(
                f"Catalogue item #{target.id} ({target.article_name}) is archived, so nothing "
                "can be merged into it."
            )
        if verdict.refusal is MergeTargetRefusal.NOT_ACTIVE:
            raise BoughtItemInactiveError(
                f"Catalogue item #{target.id} ({target.article_name}) is not active "
                f"(status={target.status.value}), so nothing can be merged into it."
            )
        return verdict.reactivates

    @staticmethod
    def assert_item_demandable(item: BoughtItem) -> None:
        """Refuses a new demand, order line or substitute for an item that is
        not active, is archived or whose PDM file is missing."""
        reason = demandable_refusal(
            status=item.status, archived=item.archived, pdm_sync_state=item.pdm_sync_state
        )
        if reason is not None:
            raise BoughtItemInactiveError(
                f"Catalogue item #{item.id} ({item.article_name}) {reason}, so no new demand, "
                "order line or substitute can name it."
            )


# ── Demand item rules ─────────────────────────────────────────────────
