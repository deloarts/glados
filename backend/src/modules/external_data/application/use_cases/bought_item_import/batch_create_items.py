"""
Validate and commit the bought-item batch create: rows parsed from a
spreadsheet on the frontend become new catalogue items.

Without the lookup, a row is created from the file: it names its
manufacturer, article groups and product family, which are resolved by
name. With the lookup, each row is looked up in the EPLAN Data Portal by
its EPLAN part number, else its order code, in one batch call; the portal
wins for every field it supplies and the file fills the rest
(_import_rows.apply_draft). A looked-up row's manufacturer is the supplier
carrying the portal's manufacturer code, never a name match; without one
the row is invalid. A number the portal does not know is `not_found`,
several hits are `ambiguous` with the candidates listed; the user pins a
candidate or creates the row from the file alone.

Every row then looks for an item that already exists (by its portal part,
GTIN, EAN, then manufacturer and normalised order code). An existing item
is treated as correct: the row is not imported and where it differs is
listed, never applied; with the lookup the item only gets the portal link
and the request for its picture. A row repeating an earlier row's key is a
duplicate. Every other row is checked by CreateBoughtItem.prepare(), the
same checks a single create runs, so `ready` means its create succeeds.

Commit re-resolves every row instead of trusting the client's last
validation, creates the ready rows and links the existing ones in one
transaction, and names every row it handled; the rest stay in the draft.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass

from src.modules.catalogue.application.facade.data_import_limits import assert_import_row_limit
from src.modules.catalogue.application.facade.item_commands import CreateBoughtItem
from src.modules.catalogue.application.mappers.bought_item_mapper import BoughtItemMapper
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.policies.bought_item_rules import BoughtItemCatalogueRules
from src.modules.catalogue.domain.value_objects.data_import_type import DataImportType
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.catalogue_queries import ArticleGroupFilterDto
from src.modules.catalogue.ports.outbound.catalogue_queries import IArticleGroupQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IProductFamilyQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ProductFamilyFilterDto
from src.modules.catalogue.ports.outbound.catalogue_queries import SupplierFilterDto
from src.modules.external_data.api import IExternalDataSettingsRepository
from src.modules.external_data.application.dto.bought_item_import_dto import BatchBoughtItemRowInput
from src.modules.external_data.application.dto.bought_item_import_dto import (
    BatchBoughtItemRowResult,
)
from src.modules.external_data.application.dto.bought_item_import_dto import (
    CommitBatchBoughtItemsResult,
)
from src.modules.external_data.application.dto.bought_item_import_dto import (
    ValidateBatchBoughtItemsResult,
)
from src.modules.external_data.application.services.edp_item_draft import EdpDraftBuilder
from src.modules.external_data.application.services.edp_link import link_edp_part
from src.modules.external_data.application.use_cases.bought_item_import._import_rows import (
    NameIndex,
)
from src.modules.external_data.application.use_cases.bought_item_import._import_rows import (
    RowValues,
)
from src.modules.external_data.application.use_cases.bought_item_import._import_rows import (
    apply_draft,
)
from src.modules.external_data.application.use_cases.bought_item_import._import_rows import (
    existing_divergences,
)
from src.modules.external_data.application.use_cases.bought_item_import._import_rows import (
    file_shape_errors,
)
from src.modules.external_data.application.use_cases.bought_item_import._import_rows import (
    lookup_key,
)
from src.modules.external_data.application.use_cases.bought_item_import._import_rows import (
    lookup_shape_errors,
)
from src.modules.external_data.application.use_cases.bought_item_import._import_rows import names
from src.modules.external_data.application.use_cases.bought_item_import._import_rows import summary
from src.modules.external_data.application.use_cases.bought_item_import._import_rows import text
from src.modules.external_data.domain.entities.admin_settings.eplan_data_portal import (
    AdminEdpSettings,
)
from src.modules.external_data.domain.errors import EdpNotConfiguredError
from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpPart
from src.modules.external_data.ports.outbound.eplan_data_portal_port import EdpConnection
from src.modules.external_data.ports.outbound.eplan_data_portal_port import IEplanDataPortalFactory
from src.modules.platform.application.services.paging import fetch_all
from src.modules.platform.application.services.retry_on_conflict import commit_with_number_retry
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


@dataclass
class _Resolved:
    result: BatchBoughtItemRowResult
    create: Callable[[], Awaitable[BoughtItem]] | None = None
    link: Callable[[], Awaitable[BoughtItem]] | None = None


@dataclass
class _Portal:
    """What one batch looked up in the portal."""

    settings: AdminEdpSettings
    builder: EdpDraftBuilder
    matches: dict[str, tuple[int, ...]]
    parts: dict[int, EdpPart]


@dataclass
class _Indexes:
    suppliers: NameIndex
    groups: NameIndex
    families: NameIndex


class _ImportRowResolver:
    """Resolves a whole batch. The name indexes and the portal lookups are
    loaded once per batch; the in-file duplicate keys accumulate over the
    rows in order."""

    def __init__(
        self,
        items: IBoughtItemCadStore,
        suppliers: ISupplierQueries,
        article_groups: IArticleGroupQueries,
        product_families: IProductFamilyQueries,
        settings: IExternalDataSettingsRepository,
        portal_factory: IEplanDataPortalFactory | None,
        create_item: CreateBoughtItem,
        bus: IEventBus,
    ) -> None:
        self._items = items
        self._bus = bus
        self._suppliers = suppliers
        self._article_groups = article_groups
        self._product_families = product_families
        self._settings = settings
        self._portal_factory = portal_factory
        self._create_item = create_item

    async def resolve_all(
        self, actor: User, rows: list[BatchBoughtItemRowInput], lookup: bool
    ) -> list[_Resolved]:
        indexes = await self._indexes()
        portal = await self._portal(rows) if lookup else None
        seen_keys: set[str] = set()
        # Sequential on purpose: the rows share one session and the
        # duplicate keys of the rows before.
        return [await self._resolve(actor, row, indexes, portal, seen_keys) for row in rows]

    async def _indexes(self) -> _Indexes:
        suppliers = await fetch_all(
            lambda skip, limit: self._suppliers.get_multi(
                SupplierFilterDto(skip=skip, limit=limit)
            ),
            MAX_PAGE_SIZE,
        )
        groups = await fetch_all(
            lambda skip, limit: self._article_groups.get_multi(
                ArticleGroupFilterDto(skip=skip, limit=limit)
            ),
            MAX_PAGE_SIZE,
        )
        families = await fetch_all(
            lambda skip, limit: self._product_families.get_multi(
                ProductFamilyFilterDto(skip=skip, limit=limit)
            ),
            MAX_PAGE_SIZE,
        )
        return _Indexes(
            suppliers=NameIndex.of([(s.id, s.name) for s in suppliers]),
            # A file may name an article group in any of its languages.
            groups=NameIndex.of([(g.id, text) for g in groups for text in g.name.values.values()]),
            families=NameIndex.of([(f.id, f.name) for f in families]),
        )

    async def _portal(self, rows: list[BatchBoughtItemRowInput]) -> _Portal:
        settings = await self._settings.get_edp()
        if not settings.enabled or not settings.pat or self._portal_factory is None:
            raise EdpNotConfiguredError("The EPLAN Data Portal is not switched on.")
        client = self._portal_factory(EdpConnection(base_url=settings.base_url, pat=settings.pat))
        keys = [key for row in rows if not row.skip_lookup and (key := lookup_key(row))]
        matches = {m.search: m.part_ids for m in await client.check_numbers(keys)}
        part_ids = {i for ids in matches.values() for i in ids}
        part_ids |= {row.edp_part_id for row in rows if row.edp_part_id is not None}
        parts = {p.part_id: p for p in await client.get_parts(sorted(part_ids))}
        builder = EdpDraftBuilder(settings, self._suppliers, self._product_families)
        return _Portal(settings=settings, builder=builder, matches=matches, parts=parts)

    async def _resolve(
        self,
        actor: User,
        row: BatchBoughtItemRowInput,
        indexes: _Indexes,
        portal: _Portal | None,
        seen_keys: set[str],
    ) -> _Resolved:
        result = BatchBoughtItemRowResult(row_index=row.row_index, row_status="invalid")
        values = RowValues.of(row)
        looked_up = portal is not None and not row.skip_lookup

        if looked_up:
            assert portal is not None
            if not await self._apply_portal(row, values, result, portal):
                return _Resolved(result)
        else:
            if errors := file_shape_errors(row):
                result.errors = errors
                return _Resolved(result)
            manufacturer_ids = indexes.suppliers.lookup(row.manufacturer_name or "")
            if len(manufacturer_ids) > 1:
                result.row_status = "ambiguous"
                result.errors = [f"Several manufacturers are named {row.manufacturer_name!r}."]
                return _Resolved(result)
            if manufacturer_ids:
                values.manufacturer_id = manufacturer_ids[0]

        if errors := self._resolve_references(row, values, indexes, portal if looked_up else None):
            result.row_status = "unresolved_reference"
            result.errors = errors
            return _Resolved(result)
        result.resolved_manufacturer_id = values.manufacturer_id
        result.resolved_article_group_ids = values.article_group_ids
        result.resolved_product_family_id = values.product_family_id

        return await self._finish(actor, values, result, seen_keys, link=looked_up)

    async def _apply_portal(
        self,
        row: BatchBoughtItemRowInput,
        values: RowValues,
        result: BatchBoughtItemRowResult,
        portal: _Portal,
    ) -> bool:
        """Resolves the row's portal part and merges it into `values`;
        False when the row stops here (its status is set)."""
        if errors := lookup_shape_errors(row):
            result.errors = errors
            return False
        language = portal.settings.language
        if row.edp_part_id is not None:
            ids: tuple[int, ...] = (row.edp_part_id,)
        else:
            ids = portal.matches.get(lookup_key(row) or "", ())
        known = [portal.parts[i] for i in ids if i in portal.parts]
        if not known:
            result.row_status = "not_found"
            result.errors = ["The EPLAN Data Portal does not know this part."]
            return False
        if len(known) > 1:
            result.row_status = "ambiguous"
            result.candidates = [summary(p, language) for p in known]
            result.errors = ["The EPLAN Data Portal knows several parts by this number."]
            return False
        part = known[0]
        draft = await portal.builder.draft(part)
        result.edp_part = summary(part, language)
        result.portal_differences = apply_draft(values, draft, text(row.manufacturer_name))
        if draft.manufacturer_id is None:
            result.errors = [
                f"No supplier has the Data Portal code {draft.manufacturer_code!r} of "
                f"{draft.manufacturer_name or 'this manufacturer'}; set it on the supplier."
            ]
            return False
        if not names(row.article_group_names):
            values.article_group_ids = list(draft.article_group_ids)
        return True

    @staticmethod
    def _resolve_references(
        row: BatchBoughtItemRowInput,
        values: RowValues,
        indexes: _Indexes,
        portal: _Portal | None,
    ) -> list[str]:
        errors: list[str] = []
        if values.manufacturer_id is None:
            errors.append(f"Manufacturer {row.manufacturer_name!r} not found.")
        group_names = names(row.article_group_names)
        if group_names:
            values.article_group_ids = []
        for name in group_names:
            ids = indexes.groups.lookup(name)
            if len(ids) == 1:
                values.article_group_ids.append(ids[0])
            else:
                errors.append(f"Article group {name!r} not found.")
        family_name = text(row.product_family_name)
        if values.product_family_id is None and family_name:
            ids = indexes.families.lookup(family_name)
            if len(ids) == 1:
                values.product_family_id = ids[0]
            elif portal is None:
                errors.append(f"Product family {family_name!r} not found.")
        return errors

    async def _finish(
        self,
        actor: User,
        values: RowValues,
        result: BatchBoughtItemRowResult,
        seen_keys: set[str],
        *,
        link: bool,
    ) -> _Resolved:
        matches = await self._existing(values)
        if len(matches) > 1:
            result.row_status = "ambiguous"
            result.errors = [
                "Several catalogue items match this row: "
                + ", ".join(f"#{m.id}" for m in matches)
                + "."
            ]
            return _Resolved(result)
        if matches:
            existing = matches[0]
            result.row_status = "exists"
            result.existing_item = BoughtItemMapper.to_result(existing)
            result.divergences = existing_divergences(values, existing)
            linker = self._linker(actor, existing, values.edp_part_id) if link else None
            return _Resolved(result, link=linker)

        keys = values.keys()
        if keys & seen_keys:
            result.row_status = "duplicate_in_file"
            result.errors = ["An earlier row of this file describes the same item."]
            return _Resolved(result)
        seen_keys.update(keys)

        try:
            create = await self._create_item.prepare(actor, values.command())
        except DomainError as exc:
            result.errors = [str(exc)]
            return _Resolved(result)
        result.row_status = "ready"
        return _Resolved(result, create=create)

    async def _existing(self, values: RowValues) -> list[BoughtItem]:
        if values.edp_part_id is not None:
            by_part = await self._items.find_by_edp_part_id(values.edp_part_id)
            if by_part:
                return by_part
        if values.gtin:
            by_gtin = await self._items.get_by_gtin(values.gtin)
            if by_gtin is not None:
                return [by_gtin]
        if values.ean:
            by_ean = await self._items.find_by_ean(values.ean)
            if by_ean:
                return by_ean
        assert values.manufacturer_id is not None
        return await self._items.find_by_order_code(
            values.manufacturer_id, values.order_code_1 or ""
        )

    def _linker(
        self, actor: User, item: BoughtItem, edp_part_id: int | None
    ) -> Callable[[], Awaitable[BoughtItem]] | None:
        """Links an existing item to its portal part, never replacing a
        different link, and requests its picture."""
        if edp_part_id is None or item.edp_part_id not in (None, edp_part_id):
            return None
        return lambda: link_edp_part(self._items, self._bus, actor, item.id, edp_part_id)


class _BatchBase:
    def __init__(
        self,
        bought_item_repo: IBoughtItemCadStore,
        supplier_repo: ISupplierQueries,
        article_group_repo: IArticleGroupQueries,
        product_family_repo: IProductFamilyQueries,
        settings_repo: IExternalDataSettingsRepository,
        *,
        create_item: CreateBoughtItem,
        event_bus: IEventBus,
        portal_factory: IEplanDataPortalFactory | None = None,
    ) -> None:
        self._settings = settings_repo
        self._resolver = _ImportRowResolver(
            bought_item_repo,
            supplier_repo,
            article_group_repo,
            product_family_repo,
            settings_repo,
            portal_factory,
            create_item,
            event_bus,
        )

    async def _resolve(
        self, actor: User, rows: list[BatchBoughtItemRowInput], lookup: bool
    ) -> list[_Resolved]:
        BoughtItemCatalogueRules.assert_can_create(actor)
        await assert_import_row_limit(self._settings, DataImportType.BOUGHT_ITEM_CREATE, len(rows))
        return await self._resolver.resolve_all(actor, rows, lookup)


class ValidateBatchBoughtItemRows(_BatchBase):
    async def execute(
        self, actor: User, rows: list[BatchBoughtItemRowInput], *, lookup: bool = False
    ) -> ValidateBatchBoughtItemsResult:
        resolved = await self._resolve(actor, rows, lookup)
        results = [r.result for r in resolved]
        return ValidateBatchBoughtItemsResult(
            results=results, ready_count=sum(1 for r in results if r.row_status == "ready")
        )


class CommitBatchBoughtItemRows(_BatchBase):
    def __init__(
        self,
        bought_item_repo: IBoughtItemCadStore,
        supplier_repo: ISupplierQueries,
        article_group_repo: IArticleGroupQueries,
        product_family_repo: IProductFamilyQueries,
        settings_repo: IExternalDataSettingsRepository,
        *,
        create_item: CreateBoughtItem,
        event_bus: IEventBus,
        uow: IUnitOfWork,
        portal_factory: IEplanDataPortalFactory | None = None,
    ) -> None:
        super().__init__(
            bought_item_repo,
            supplier_repo,
            article_group_repo,
            product_family_repo,
            settings_repo,
            create_item=create_item,
            event_bus=event_bus,
            portal_factory=portal_factory,
        )
        self._uow = uow

    async def execute(
        self, actor: User, rows: list[BatchBoughtItemRowInput], *, lookup: bool = False
    ) -> CommitBatchBoughtItemsResult:
        resolved = await self._resolve(actor, rows, lookup)
        creates = [(r.result.row_index, r.create) for r in resolved if r.create is not None]
        links = [(r.result.row_index, r.link) for r in resolved if r.link is not None]
        handled = sorted(
            r.result.row_index for r in resolved if r.result.row_status in ("ready", "exists")
        )
        if not creates and not links:
            return CommitBatchBoughtItemsResult(handled_row_indexes=handled)

        async def write_all() -> tuple[list[BoughtItem], list[BoughtItem]]:
            # Every closure publishes its events before the commit below, so
            # the items, their links and their events commit together.
            created = [await create() for _, create in creates if create is not None]
            linked = [await link() for _, link in links if link is not None]
            return created, linked

        created, linked = await commit_with_number_retry(self._uow, write_all)
        log.info(f"Batch created {len(created)} and linked {len(linked)} catalogue item(s).")
        return CommitBatchBoughtItemsResult(
            created_item_ids=[item.id for item in created],
            linked_item_ids=[item.id for item in linked],
            created_row_indexes=[index for index, _ in creates],
            handled_row_indexes=handled,
        )
