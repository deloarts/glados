"""
Business rules for the made item catalogue aggregate. No I/O. No ORM.
"""

from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.domain.errors import MadeItemCustomerDataInvalidError
from src.modules.catalogue.domain.errors import MadeItemInactiveError
from src.modules.catalogue.domain.errors import MadeItemNotNewestRevisionError
from src.modules.catalogue.domain.errors import MadeItemProcessGroupingInvalidError
from src.modules.catalogue.domain.policies import revision_scheme
from src.modules.catalogue.domain.policies.catalogue_item_status import MergeTargetRefusal
from src.modules.catalogue.domain.policies.catalogue_item_status import demandable_refusal
from src.modules.catalogue.domain.policies.catalogue_item_status import merge_target_verdict
from src.modules.catalogue.domain.policies.material_source_rules import (
    assert_at_most_one_material_source as _assert_at_most_one_material_source,
)
from src.modules.catalogue.domain.policies.step_role_rules import assert_role_matches_methods
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.services.grouping_rules import validate_contiguous_grouping
from src.modules.platform.domain.value_objects.permission import Permission


class MadeItemCatalogueRules:
    @staticmethod
    def assert_can_create(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_MADE_ITEMS, "create", "catalogue items")

    @staticmethod
    def assert_can_update(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_MADE_ITEMS, "update", "catalogue items")

    @staticmethod
    def assert_can_archive(actor: User) -> None:
        assert_has_permission(actor, Permission.DELETE_MADE_ITEMS, "archive", "catalogue items")

    @staticmethod
    def assert_can_restore(actor: User) -> None:
        assert_has_permission(actor, Permission.DELETE_MADE_ITEMS, "restore", "catalogue items")

    @staticmethod
    def assert_item_active(item: MadeItem) -> None:
        if item.status != MadeItemCatalogueStatus.ACTIVE.value:
            raise MadeItemInactiveError(
                f"Catalogue item #{item.id} ({item.article_name}) is not active "
                f"(status={item.status.value})."
            )

    @staticmethod
    def demandable_refusal(item: MadeItem) -> str | None:
        """Why a new demand or lot may not name the item, None when it may."""
        return demandable_refusal(
            status=item.status, archived=item.archived, pdm_sync_state=item.pdm_sync_state
        )

    @staticmethod
    def assert_merge_target(target: MadeItem, source: MadeItem) -> bool:
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
            raise MadeItemInactiveError(
                f"Catalogue item #{target.id} ({target.article_name}) is archived, so nothing "
                "can be merged into it."
            )
        if verdict.refusal is MergeTargetRefusal.NOT_ACTIVE:
            raise MadeItemInactiveError(
                f"Catalogue item #{target.id} ({target.article_name}) is not active "
                f"(status={target.status.value}), so nothing can be merged into it."
            )
        return verdict.reactivates

    @staticmethod
    def assert_item_demandable(item: MadeItem) -> None:
        """Refuses a new demand or lot for an item that is not active, is
        archived or whose PDM file is missing."""
        reason = MadeItemCatalogueRules.demandable_refusal(item)
        if reason is not None:
            raise MadeItemInactiveError(
                f"Catalogue item #{item.id} ({item.article_name}) {reason}, so no new demand "
                "or lot can name it."
            )

    @staticmethod
    def assert_at_most_one_material_source(
        bought_item_id: int | None, source_item_id: int | None
    ) -> None:
        _assert_at_most_one_material_source(bought_item_id, source_item_id)

    @staticmethod
    def assert_customer_data_complete(
        customer_id: int | None, customer_part_number: str | None, customer_revision: str | None
    ) -> None:
        """A customer item names its customer and the customer's part number,
        and customer data never stands without a customer. Web and `pat`
        writes only; PDM ingest stores whatever the datacard holds."""
        if customer_id is None:
            if customer_part_number or customer_revision:
                raise MadeItemCustomerDataInvalidError(
                    "A customer part number or customer revision needs a customer."
                )
            return
        if not customer_part_number:
            raise MadeItemCustomerDataInvalidError(
                f"Customer #{customer_id} is set, so the customer part number is required."
            )


# ── Revisions ────────────────────────────────────────────────────────────


def newest_of(items: list[MadeItem]) -> MadeItem:
    """Selects the "newest" item: highest (len(revision), revision)
    (revision_scheme.sort_key), ties broken by created desc then id desc.
    This ordering matches the SQL window (made_item_repository/item.py's
    `latest_only` filter) so the two never disagree. `items` must be
    non-empty; callers pass a family (get_revisions), which always
    includes the row they started from."""
    return max(items, key=lambda i: (revision_scheme.sort_key(i.revision), i.created, i.id))


def assert_editable(item: MadeItem, siblings: list[MadeItem], only_newest_editable: bool) -> None:
    """Enforces editability without status exemption: used by the process
    and file mutation use cases, which never change status themselves, so
    the UpdateMadeItem-only status carve-out does not apply here. A NULL
    `part_number` item has no family to rank against and is always
    editable; `siblings` should be `item`'s non-deleted family
    (get_revisions(item.part_number)), item included."""
    if not only_newest_editable or item.part_number is None:
        return
    if newest_of(siblings).id != item.id:
        raise MadeItemNotNewestRevisionError(
            f"Catalogue item #{item.id} is not the newest revision of part number "
            f"{item.part_number!r} and only_newest_editable is on."
        )


# ── Step role ─────────────────────────────────────────────────────────────


def assert_valid_step_role(
    role: str, fabrication_method_id: int | None, inspection_method_id: int | None
) -> None:
    """Mirrors ck_made_item_process_role_method / ck_made_item_process_
    inspection_method: a FABRICATION-role process must have a
    fabrication_method_id and no inspection_method_id; an INSPECTION-role
    process must have an inspection_method_id and no fabrication_method_id."""
    assert_role_matches_methods(
        role,
        fabrication_method_id,
        inspection_method_id,
        error=MadeItemProcessGroupingInvalidError,
        noun="process",
    )


# ── Process grouping ─────────────────────────────────────────────────────


def validate_process_grouping(processes: list[MadeItemProcess], groups: list[list[int]]) -> None:
    """`groups` is an ordered list of process-id lists, one per intended
    routing group, in timeline order. Raises MadeItemProcessGroupingInvalidError
    unless every process appears in exactly one group and, sorted by
    position, the groups form contiguous, gapless, correctly-ordered
    slices of the process list.

    An inspection-role process can never share a group with any other
    process (fabrication or inspection): a QA checkpoint is always its own
    lot position, never folded into a fabrication position. Delegates to
    grouping_rules.validate_contiguous_grouping, shared with
    lot_rules.validate_position_grouping."""
    validate_contiguous_grouping(
        processes,
        groups,
        item_id=lambda p: p.id,
        item_order=lambda p: p.position,
        is_inspection=lambda p: p.role == StepRole.INSPECTION,
        error_factory=MadeItemProcessGroupingInvalidError,
        item_noun="process",
        group_noun="process group",
        owner_noun="this made item",
        order_noun="position",
    )


def normalize_process_groups(ordered: list[MadeItemProcess]) -> list[int]:
    """Recomputes contiguous, 0-based group indexes for processes already in
    their final position order, preserving adjacent same-group runs and
    splitting any run that was torn apart (e.g. by a reorder or a delete):
    a new group starts whenever a process's current group_index differs
    from its predecessor's."""
    result: list[int] = []
    next_index = -1
    prev_group_index: int | None = None
    for process in ordered:
        if prev_group_index is None or process.group_index != prev_group_index:
            next_index += 1
        result.append(next_index)
        prev_group_index = process.group_index
    return result
