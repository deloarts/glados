"""
Updates catalogue item metadata with part-number renumbering, GTIN/EAN
validation, and conflict retry logic. Status and successor are checked
together (src/modules/catalogue/domain/policies/catalogue_item_status.py), and a status
change publishes BoughtItemStatusChanged.
"""

from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.catalogue.application.dto.bought_item_dto import UpdateBoughtItemCommand
from src.modules.catalogue.application.mappers.bought_item_mapper import BoughtItemMapper
from src.modules.catalogue.application.services.catalogue_successor import resolve_successor
from src.modules.catalogue.application.services.item_delivery_tolerance import (
    assert_valid_item_tolerances,
)
from src.modules.catalogue.application.services.item_delivery_tolerance import (
    keep_unsent_tolerances,
)
from src.modules.catalogue.application.services.product_family_lookup import (
    assert_product_family_exists,
)
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.errors import ArticleGroupNotFoundError
from src.modules.catalogue.domain.errors import BoughtItemGtinDuplicateError
from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.errors import BoughtItemPartNumberDuplicateError
from src.modules.catalogue.domain.errors import BoughtItemPartNumberNotEditableError
from src.modules.catalogue.domain.errors import PdmSuccessorRequiresReplacedStatusError
from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.catalogue.domain.events.bought_item_events import BoughtItemStatusChanged
from src.modules.catalogue.domain.policies.bought_item_rules import BoughtItemCatalogueRules
from src.modules.catalogue.domain.policies.catalogue_item_status import CatalogueStatusChange
from src.modules.catalogue.domain.policies.pdm_ownership import assert_cad_row_writable
from src.modules.catalogue.domain.policies.pdm_ownership import assert_part_number_not_pdm_reserved
from src.modules.catalogue.domain.policies.pdm_ownership import blocked_pdm_owned_changes
from src.modules.catalogue.domain.policies.pdm_ownership import pdm_locked_fields
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.ports.outbound.cad_source_port import ICadSource
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.catalogue.ports.outbound.repositories.article_group_repository import (
    IArticleGroupRepository,
)
from src.modules.catalogue.ports.outbound.repositories.bought_item_repository import (
    IBoughtItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.part_number_registry import (
    IPartNumberRegistry,
)
from src.modules.catalogue.ports.outbound.repositories.product_family_repository import (
    IProductFamilyRepository,
)
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.platform.application.services.command_changelog import diff_command
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.retry_on_conflict import commit_with_number_retry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class UpdateBoughtItem:
    def __init__(
        self,
        bought_item_repo: IBoughtItemRepository,
        supplier_repo: ISupplierRepository,
        article_group_repo: IArticleGroupRepository,
        admin_settings_repo: ICatalogueSettingsRepository,
        *,
        cad_source: ICadSource,
        part_number_registry: IPartNumberRegistry,
        uow: IUnitOfWork,
        # None only for unit tests that predate the status event; the deps
        # factory always passes the transactional bus.
        event_bus: IEventBus | None = None,
        # None only for unit tests that predate the field; the deps factory
        # always passes it.
        product_family_repo: IProductFamilyRepository | None = None,
    ) -> None:
        self._product_families = product_family_repo
        self._items = bought_item_repo
        self._suppliers = supplier_repo
        self._article_groups = article_group_repo
        self._admin_settings = admin_settings_repo
        self._cad = cad_source
        self._registry = part_number_registry
        self._uow = uow
        self._bus = event_bus

    async def execute(
        self, actor: User, item_id: int, cmd: UpdateBoughtItemCommand
    ) -> BoughtItemResult:
        BoughtItemCatalogueRules.assert_can_update(actor)

        await self._items.lock_for_update(item_id)
        item = found_or_raise(
            await self._items.get_by_id(item_id),
            BoughtItemNotFoundError,
            f"Catalogue item #{item_id} not found.",
        )
        assert_edit_version(item, cmd.expected_edit_version, what=f"Catalogue item #{item.id}")
        cmd = keep_unsent_tolerances(cmd, item)
        assert_valid_item_tolerances(cmd)

        if not await self._suppliers.get_by_id(cmd.manufacturer_id):
            raise SupplierNotFoundError(f"Supplier #{cmd.manufacturer_id} not found.")

        order_settings = await self._admin_settings.get_orders()
        cad = await self._cad.policy()

        # PDM-owned field enforcement (docs/FIELD_OWNERSHIP.md principle 3):
        # see update_made_item.py's matching comment, which covers renumbering too,
        # since part_number is PDM-owned.
        enforce = cad.enforces_ownership_for(actor)
        assert_cad_row_writable(
            enforce=enforce,
            item_data_source=item.data_source,
            blocked=blocked_pdm_owned_changes("bought", item, cmd.model_dump()),
        )

        # `status` is itself PDM-owned on a CAD row while enforcement is
        # active; see update_made_item.py's matching comment for the same rule.
        if (
            enforce
            and item.data_source == DataSource.CAD.value
            and cmd.successor_item_id is not None
            and cmd.successor_item_id != item.successor_item_id
            and item.status != BoughtItemCatalogueStatus.REPLACED.value
        ):
            raise PdmSuccessorRequiresReplacedStatusError(
                f"Catalogue item #{item_id}: status is managed by PDM; move the file to a "
                "replaced state before assigning a successor here."
            )

        # From here on the command carries the successor the item keeps.
        cmd = cmd.model_copy(
            update={"successor_item_id": await self._resolve_successor(item, cmd, enforce)}
        )

        renumbering = cmd.part_number != item.part_number
        if renumbering and not order_settings.part_number_editable:
            raise BoughtItemPartNumberNotEditableError(
                f"Catalogue item #{item_id}'s part number cannot be changed."
            )
        if renumbering and cmd.part_number is not None:
            # Checked once up front; see create_made_item.py's matching
            # comment.
            assert_part_number_not_pdm_reserved(
                cmd.part_number, order_settings.pdm_part_number_pattern, enabled=cad.connected
            )

        if (
            cmd.gtin != item.gtin
            and cmd.gtin is not None
            and await self._items.get_by_gtin(cmd.gtin)
        ):
            raise BoughtItemGtinDuplicateError(f"GTIN {cmd.gtin!r} is already in use.")

        if cmd.article_group_ids:
            found = await self._article_groups.get_by_ids(cmd.article_group_ids)
            if len(found) != len(set(cmd.article_group_ids)):
                missing = set(cmd.article_group_ids) - {g.id for g in found}
                raise ArticleGroupNotFoundError(f"Article group(s) {missing} not found.")

        if cmd.product_family_id != item.product_family_id:
            await assert_product_family_exists(self._product_families, cmd.product_family_id)

        async def _apply_and_save() -> BoughtItem:
            old_status = item.status
            changelog_entry = diff_command(item, cmd)

            item.order_code_1 = cmd.order_code_1
            item.order_code_2 = cmd.order_code_2
            item.gtin = cmd.gtin
            item.ean = cmd.ean
            item.tariff_number = cmd.tariff_number
            item.article_name = cmd.article_name
            item.article_group_ids = cmd.article_group_ids
            item.status = BoughtItemCatalogueStatus(cmd.status)
            item.part_number = cmd.part_number
            item.mass = cmd.mass
            item.note = cmd.note
            item.weblink = cmd.weblink
            item.manufacturer_id = cmd.manufacturer_id
            item.product_family_id = cmd.product_family_id
            item.over_delivery_tolerance_percent = cmd.over_delivery_tolerance_percent
            item.under_delivery_tolerance_percent = cmd.under_delivery_tolerance_percent
            item.successor_item_id = cmd.successor_item_id
            item.changed = now_utc()
            item.changes = append_changelog(item.changes, actor.full_name, changelog_entry)
            saved_item = await self._items.save(item)
            await self._publish_status_change(actor, old_status, saved_item)
            return saved_item

        if not renumbering:
            saved = await _apply_and_save()
            await self._uow.commit()
        else:
            new_pn = cmd.part_number
            old_pn = item.part_number

            async def write() -> BoughtItem:
                if new_pn is not None:
                    # claim() before save, in the same transaction.
                    await self._registry.claim(new_pn, "bought")
                    # part_number is unconditionally unique; claim() above
                    # already blocks any part number already in use, so
                    # this mainly guards against a registry/table
                    # mismatch.
                    existing = await self._items.get_by_part_number(new_pn)
                    if existing is not None and existing.id != item.id:
                        raise BoughtItemPartNumberDuplicateError(
                            f"Part number {new_pn!r} is already in use."
                        )

                result = await _apply_and_save()

                # Only after `item` has actually moved off `old_pn`; see
                # update_made_item.py's matching comment.
                if old_pn is not None:
                    await self._registry.release_if_unused(old_pn)

                return result

            # commit_with_number_retry(..., attempts=1): see
            # update_made_item.py's matching comment: `item` is an
            # already-persisted aggregate a blind full replay could leave
            # inconsistent (never retried), but IPartNumberRegistry.claim()/
            # release_if_unused() flush eagerly and can raise the
            # IntegrityError themselves, so only wrapping the whole
            # `write()` (not just a bare commit_or_raise_numbering_conflict)
            # catches that.
            saved = await commit_with_number_retry(self._uow, write, attempts=1)

        log.info(f"Updated catalogue item {saved.article_name!r}, ID={saved.id}.")
        result = BoughtItemMapper.to_result(saved)
        # Same `enforce` already computed above for assert_cad_row_writable, since
        # the two must never disagree about which fields are locked.
        result.pdm_locked_fields = pdm_locked_fields(
            kind="bought", enforce=enforce, item_data_source=saved.data_source
        )
        return result

    async def _resolve_successor(
        self, item: BoughtItem, cmd: UpdateBoughtItemCommand, enforce: bool
    ) -> int | None:
        """The successor the item keeps, after the status rule accepted the
        write. On an enforced CAD row PDM owns the status."""
        return await resolve_successor(
            CatalogueStatusChange(
                family="bought item",
                item_id=item.id,
                old_status=item.status,
                old_successor_id=item.successor_item_id,
                new_status=BoughtItemCatalogueStatus(cmd.status),
                requested_successor_id=cmd.successor_item_id,
                status_owned_by_pdm=enforce and item.data_source == DataSource.CAD.value,
            ),
            self._items.get_by_id,
        )

    async def _publish_status_change(self, actor: User, old_status: str, saved: BoughtItem) -> None:
        if self._bus is None or saved.status == old_status:
            return
        await self._bus.publish(
            BoughtItemStatusChanged(
                item_id=saved.id,
                article_name=saved.article_name,
                old_status=BoughtItemCatalogueStatus(old_status),
                new_status=BoughtItemCatalogueStatus(saved.status),
                actor_id=actor.id,
            )
        )
