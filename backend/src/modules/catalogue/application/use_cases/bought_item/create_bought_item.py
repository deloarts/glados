"""
Creates a bought item with optional auto-generated part number, enforcing uniqueness and PDM
integration rules.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import datetime

from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.catalogue.application.dto.bought_item_dto import CreateBoughtItemCommand
from src.modules.catalogue.application.mappers.bought_item_mapper import BoughtItemMapper
from src.modules.catalogue.application.services.item_delivery_tolerance import (
    assert_valid_item_tolerances,
)
from src.modules.catalogue.application.services.product_family_lookup import (
    assert_product_family_exists,
)
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.errors import ArticleGroupNotFoundError
from src.modules.catalogue.domain.errors import BoughtItemGtinDuplicateError
from src.modules.catalogue.domain.errors import BoughtItemPartNumberDuplicateError
from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.catalogue.domain.errors import WebCreationDisabledError
from src.modules.catalogue.domain.events.bought_item_events import BoughtItemCreated
from src.modules.catalogue.domain.events.bought_item_events import BoughtItemEdpPictureRequested
from src.modules.catalogue.domain.policies.bought_item_rules import BoughtItemCatalogueRules
from src.modules.catalogue.domain.policies.catalogue_item_status import assert_new_item_status
from src.modules.catalogue.domain.policies.pdm_ownership import assert_part_number_not_pdm_reserved
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
from src.modules.platform.application.services.retry_on_conflict import commit_with_number_retry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class CreateBoughtItem:
    """Creates a bought item for the web and PAT surfaces. `execute()`
    splits into `prepare()`, which runs every pre-check and returns the
    non-committing `write` closure, and the commit itself: IngestPdmFile
    (application.use_cases.pdm.ingest_pdm_file) reuses `prepare()` to fold
    this same closure into its own larger transaction, alongside the PDM
    link-column write, instead of committing separately."""

    def __init__(
        self,
        bought_item_repo: IBoughtItemRepository,
        supplier_repo: ISupplierRepository,
        article_group_repo: IArticleGroupRepository,
        admin_settings_repo: ICatalogueSettingsRepository,
        *,
        cad_source: ICadSource,
        part_number_registry: IPartNumberRegistry,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        # None only where no caller can set a product family (PDM ingest,
        # unit tests that predate the field); the web and PAT factories pass it.
        product_family_repo: IProductFamilyRepository | None = None,
    ) -> None:
        self._items = bought_item_repo
        self._product_families = product_family_repo
        self._suppliers = supplier_repo
        self._article_groups = article_group_repo
        self._admin_settings = admin_settings_repo
        self._cad = cad_source
        self._registry = part_number_registry
        self._bus = event_bus
        self._uow = uow

    async def prepare(
        self, actor: User, cmd: CreateBoughtItemCommand
    ) -> Callable[[], Awaitable[BoughtItem]]:
        """Runs every pre-check (permissions, supplier/article-group
        existence, settings lookups, the hand-typed-number-vs-PDM-pattern
        guard, the gtin-duplicate check) and returns the `write` closure
        that claims the part number, checks for a duplicate, builds the
        entity and publishes BoughtItemCreated, without committing. See
        this class's docstring for why the split exists."""
        BoughtItemCatalogueRules.assert_can_create(actor)
        assert_new_item_status(family="bought item", status=BoughtItemCatalogueStatus(cmd.status))
        await self._assert_references_exist(cmd)

        order_settings = await self._admin_settings.get_orders()
        pdm_enabled = (await self._cad.policy()).connected
        self._assert_part_number_allowed(actor, cmd, order_settings, pdm_enabled)

        if cmd.gtin is not None and await self._items.get_by_gtin(cmd.gtin) is not None:
            raise BoughtItemGtinDuplicateError(f"GTIN {cmd.gtin!r} is already in use.")

        now = now_utc()

        async def write() -> BoughtItem:
            return await self._write(actor, cmd, order_settings, now)

        return write

    async def _assert_references_exist(self, cmd: CreateBoughtItemCommand) -> None:
        if not await self._suppliers.get_by_id(cmd.manufacturer_id):
            raise SupplierNotFoundError(f"Supplier #{cmd.manufacturer_id} not found.")

        if cmd.article_group_ids:
            found = await self._article_groups.get_by_ids(cmd.article_group_ids)
            if len(found) != len(set(cmd.article_group_ids)):
                missing = set(cmd.article_group_ids) - {g.id for g in found}
                raise ArticleGroupNotFoundError(f"Article group(s) {missing} not found.")

        await assert_product_family_exists(self._product_families, cmd.product_family_id)
        assert_valid_item_tolerances(cmd)

    @staticmethod
    def _assert_part_number_allowed(
        actor: User,
        cmd: CreateBoughtItemCommand,
        order_settings: AdminOrderSettings,
        pdm_enabled: bool,
    ) -> None:
        # Web creation of bought items while PDM is enabled is an admin choice.
        # Ingest, as the system user, is the PDM path itself and is exempt.
        if pdm_enabled and not order_settings.web_creation_allowed and not actor.is_systemuser:
            raise WebCreationDisabledError(
                "Web creation of bought items is disabled while the PDM integration is enabled."
            )

        if (
            not order_settings.part_number_auto
            and cmd.part_number is not None
            and not actor.is_systemuser
        ):
            # Checked once up front; see create_made_item.py for the matching
            # rationale, including the system-user exemption for IngestPdmFile.
            assert_part_number_not_pdm_reserved(
                cmd.part_number, order_settings.pdm_part_number_pattern, enabled=pdm_enabled
            )

    async def _write(
        self,
        actor: User,
        cmd: CreateBoughtItemCommand,
        order_settings: AdminOrderSettings,
        now: datetime,
    ) -> BoughtItem:
        # Re-derived on every attempt (including a retry); see
        # create_made_item.py's matching comment for why this must live
        # inside `_write()` rather than be computed once before it runs.
        # Ingest, as the system user, brings PDM's own number, which
        # auto-numbering must never replace.
        if order_settings.part_number_auto and not (
            actor.is_systemuser and cmd.part_number is not None
        ):
            part_number: str | None = await self._registry.next_part_number(
                order_settings.part_number_format
            )
        else:
            part_number = cmd.part_number

        # Every non-null part number registers a brand-new number in the
        # same transaction, before save.
        if part_number is not None:
            await self._registry.claim(part_number, "bought")

        # Part number is unconditionally unique; claim() above already
        # blocks any part number already in use, so this mainly guards
        # against a registry/table mismatch.
        if (
            part_number is not None
            and await self._items.get_by_part_number(part_number) is not None
        ):
            raise BoughtItemPartNumberDuplicateError(
                f"Part number {part_number!r} is already in use."
            )

        item = BoughtItem(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Catalogue item created."),
            archived=False,
            order_code_1=cmd.order_code_1,
            order_code_2=cmd.order_code_2,
            gtin=cmd.gtin,
            ean=cmd.ean,
            tariff_number=cmd.tariff_number,
            status=BoughtItemCatalogueStatus(cmd.status),
            article_name=cmd.article_name,
            data_source=DataSource(cmd.data_source),
            part_number=part_number,
            mass=cmd.mass,
            successor_item_id=None,
            article_group_ids=cmd.article_group_ids,
            note=cmd.note,
            weblink=cmd.weblink,
            files=[],
            creator_id=actor.id,
            approver_id=None,
            manufacturer_id=cmd.manufacturer_id,
            product_family_id=cmd.product_family_id,
            over_delivery_tolerance_percent=cmd.over_delivery_tolerance_percent,
            under_delivery_tolerance_percent=cmd.under_delivery_tolerance_percent,
            edp_part_id=cmd.edp_part_id,
            edp_synced_at=now if cmd.edp_part_id is not None else None,
            creator=actor,
        )

        saved = await self._items.save(item)

        await self._bus.publish(
            BoughtItemCreated(
                item_id=saved.id,
                article_name=saved.article_name,
                creator_id=saved.creator_id,
            )
        )
        if saved.edp_part_id is not None:
            await self._bus.publish(BoughtItemEdpPictureRequested(item_id=saved.id))
        return saved

    async def execute(self, actor: User, cmd: CreateBoughtItemCommand) -> BoughtItemResult:
        write = await self.prepare(actor, cmd)

        # commit_with_number_retry: see create_made_item.py's matching
        # comment. `write()` is a brand-new item fully reconstructible
        # from `cmd`, and IPartNumberRegistry.claim() flushes eagerly, so
        # only wrapping the whole `write()` (not just a final commit)
        # catches a conflict it raises itself.
        saved = await commit_with_number_retry(self._uow, write)

        log.info(f"Created catalogue item {saved.article_name!r}, ID={saved.id}.")

        return BoughtItemMapper.to_result(saved)
