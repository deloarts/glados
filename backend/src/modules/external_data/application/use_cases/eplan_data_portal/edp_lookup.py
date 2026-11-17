"""
The EPLAN Data Portal on single bought items:

- SearchEdpParts backs the search in the create dialog: ranked portal hits,
  each with the values it would fill (application.services.edp_item_draft)
  and the catalogue item that already describes it, if any.
- MatchEdpParts gives the same hits for the parts an order, type or EPLAN
  part number names exactly, for the SolidWorks add-in, which looks up the
  order code an engineer typed. Several makers can share a number, so a
  given manufacturer narrows the hits to its Data Portal code.
- GetEdpAvailability says whether the portal is switched on, so a client
  can hide what would only fail.
- LookupBoughtItemInEdp compares an existing item with its portal part:
  the part it is linked to, else the part its order code finds, narrowed to
  its manufacturer's Data Portal code. Several hits come back as candidates
  to pick from. Each compared field says whether the portal value may be
  written: a field PDM owns on this row is shown, never applicable.
- GetEdpPartPicture passes a part's picture through, since the browser
  loads images from Glados' own origin only.
- ApplyEdpLookup writes the chosen portal values through UpdateBoughtItem,
  so every rule of a web edit applies (PDM ownership included), then links
  the item to the part and requests its picture.

The search, the match and the picture need use:data_portal, since each
spends the organisation's portal token; the lookup on an item and its apply
action need write:bought_items, and so does creating an item from a hit,
which goes through the normal bought item create.

An item already in the catalogue is never changed by the search or the
import; the lookup on an item is the one place where the user chooses to
take the portal's values.
"""

from dataclasses import dataclass

from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.catalogue.application.dto.bought_item_dto import UpdateBoughtItemCommand
from src.modules.catalogue.application.facade.item_commands import UpdateBoughtItem
from src.modules.catalogue.application.mappers.bought_item_mapper import BoughtItemMapper
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.policies.bought_item_rules import BoughtItemCatalogueRules
from src.modules.catalogue.domain.policies.pdm_ownership import pdm_locked_fields
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.catalogue_queries import IProductFamilyQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.external_data.application.dto.bought_item_edp_dto import ApplyEdpLookupCommand
from src.modules.external_data.application.dto.bought_item_edp_dto import EdpAvailabilityResult
from src.modules.external_data.application.dto.bought_item_edp_dto import EdpItemDraftResult
from src.modules.external_data.application.dto.bought_item_edp_dto import EdpItemLookupResult
from src.modules.external_data.application.dto.bought_item_edp_dto import EdpLookupField
from src.modules.external_data.application.dto.bought_item_edp_dto import EdpLookupFieldResult
from src.modules.external_data.application.dto.bought_item_edp_dto import EdpSearchHitResult
from src.modules.external_data.application.dto.bought_item_edp_dto import EdpSearchResult
from src.modules.external_data.application.services.edp_item_draft import EdpDraftBuilder
from src.modules.external_data.application.services.edp_item_draft import EdpItemDraft
from src.modules.external_data.application.services.edp_link import link_edp_part
from src.modules.external_data.application.services.pdm_integration import is_pdm_enabled
from src.modules.external_data.application.use_cases.bought_item_import._import_rows import summary
from src.modules.external_data.domain.entities.admin_settings.eplan_data_portal import (
    AdminEdpSettings,
)
from src.modules.external_data.domain.errors import EdpNotConfiguredError
from src.modules.external_data.domain.errors import EdpPartNotFoundError
from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpPart
from src.modules.external_data.ports.outbound.eplan_data_portal_port import EdpConnection
from src.modules.external_data.ports.outbound.eplan_data_portal_port import IEplanDataPortal
from src.modules.external_data.ports.outbound.eplan_data_portal_port import IEplanDataPortalFactory
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.platform.application.services.import_text import norm
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

SEARCH_LIMIT = 20


def draft_result(draft: EdpItemDraft) -> EdpItemDraftResult:
    return EdpItemDraftResult(
        edp_part_id=draft.edp_part_id,
        article_name=draft.article_name,
        order_code_1=draft.order_code_1,
        order_code_2=draft.order_code_2,
        ean=draft.ean,
        weblink=draft.weblink,
        manufacturer_code=draft.manufacturer_code,
        manufacturer_id=draft.manufacturer_id,
        product_family_name=draft.product_family_name,
        product_family_id=draft.product_family_id,
        article_group_ids=list(draft.article_group_ids),
    )


@dataclass
class _EdpAccess:
    settings: AdminEdpSettings
    client: IEplanDataPortal
    builder: EdpDraftBuilder


class _EdpUseCase:
    def __init__(
        self,
        bought_item_repo: IBoughtItemCadStore,
        supplier_repo: ISupplierQueries,
        product_family_repo: IProductFamilyQueries,
        settings_repo: IExternalDataSettingsRepository,
        portal_factory: IEplanDataPortalFactory,
    ) -> None:
        self._items = bought_item_repo
        self._suppliers = supplier_repo
        self._families = product_family_repo
        self._settings = settings_repo
        self._portal_factory = portal_factory

    async def _access(self) -> _EdpAccess:
        settings = await self._settings.get_edp()
        if not settings.enabled or not settings.pat:
            raise EdpNotConfiguredError("The EPLAN Data Portal is not switched on.")
        client = self._portal_factory(EdpConnection(base_url=settings.base_url, pat=settings.pat))
        builder = EdpDraftBuilder(settings, self._suppliers, self._families)
        return _EdpAccess(settings=settings, client=client, builder=builder)

    async def _item(self, item_id: int) -> BoughtItem:
        return found_or_raise(
            await self._items.get_by_id(item_id),
            BoughtItemNotFoundError,
            f"Catalogue item #{item_id} not found.",
        )

    async def _hits(self, access: _EdpAccess, parts: list[EdpPart]) -> EdpSearchResult:
        hits: list[EdpSearchHitResult] = []
        for part in parts:
            draft = await access.builder.draft(part)
            existing = await self._existing(draft)
            hits.append(
                EdpSearchHitResult(
                    part=summary(part, access.settings.language),
                    draft=draft_result(draft),
                    existing_item=BoughtItemMapper.to_result(existing) if existing else None,
                )
            )
        return EdpSearchResult(hits=hits)

    async def _existing(self, draft: EdpItemDraft) -> BoughtItem | None:
        linked = await self._items.find_by_edp_part_id(draft.edp_part_id)
        if linked:
            return linked[0]
        if draft.manufacturer_id is not None and draft.order_code_1:
            by_code = await self._items.find_by_order_code(
                draft.manufacturer_id, draft.order_code_1
            )
            if by_code:
                return by_code[0]
        return None


def _assert_can_use_portal(actor: User) -> None:
    assert_has_permission(actor, Permission.USE_DATA_PORTAL, "use", "the EPLAN Data Portal")


def _same_maker(parts: list[EdpPart], supplier: Supplier | None) -> list[EdpPart]:
    """Of several parts, the ones of the supplier's Data Portal code; all of
    them when it has none or none match."""
    if supplier is None or not supplier.edp_code or len(parts) < 2:
        return parts
    same = [p for p in parts if (p.manufacturer_code or "").upper() == supplier.edp_code]
    return same or parts


class SearchEdpParts(_EdpUseCase):
    async def execute(self, actor: User, query: str, limit: int = SEARCH_LIMIT) -> EdpSearchResult:
        _assert_can_use_portal(actor)
        access = await self._access()
        parts = await access.client.search(query, max(1, min(limit, SEARCH_LIMIT)))
        return await self._hits(access, parts)


class MatchEdpParts(_EdpUseCase):
    async def execute(
        self, actor: User, number: str, manufacturer_id: int | None = None
    ) -> EdpSearchResult:
        _assert_can_use_portal(actor)
        access = await self._access()
        matches = await access.client.check_numbers([number.strip()])
        ids = list(matches[0].part_ids[:SEARCH_LIMIT]) if matches else []
        parts = await access.client.get_parts(ids) if ids else []
        if manufacturer_id is not None:
            parts = _same_maker(parts, await self._suppliers.get_by_id(manufacturer_id))
        return await self._hits(access, parts)


class GetEdpAvailability:
    """Whether the portal is switched on and has a token, without revealing
    anything else of its settings."""

    def __init__(self, settings_repo: IExternalDataSettingsRepository) -> None:
        self._settings = settings_repo

    async def execute(self) -> EdpAvailabilityResult:
        settings = await self._settings.get_edp()
        return EdpAvailabilityResult(enabled=settings.enabled and bool(settings.pat))


class GetEdpPartPicture(_EdpUseCase):
    """The product picture of a portal part, passed through Glados so the
    browser only ever loads images from its own origin."""

    async def execute(self, actor: User, part_id: int) -> bytes:
        _assert_can_use_portal(actor)
        access = await self._access()
        parts = await access.client.get_parts([part_id])
        url = parts[0].picture_url if parts else None
        picture = await access.client.fetch_picture(url) if url else None
        if picture is None:
            raise EdpPartNotFoundError(f"EPLAN Data Portal part #{part_id} has no picture.")
        return picture


class LookupBoughtItemInEdp(_EdpUseCase):
    async def execute(
        self, actor: User, item_id: int, part_id: int | None = None
    ) -> EdpItemLookupResult:
        BoughtItemCatalogueRules.assert_can_update(actor)
        item = await self._item(item_id)
        access = await self._access()
        language = access.settings.language
        result = EdpItemLookupResult(item_id=item.id)

        candidates = await self._candidates(access, item, part_id)
        if not candidates:
            result.errors = ["The EPLAN Data Portal does not know this item."]
            return result
        if len(candidates) > 1:
            result.candidates = [summary(p, language) for p in candidates]
            return result

        part = candidates[0]
        draft = await access.builder.draft(part)
        result.part = summary(part, language)
        result.fields = await self._compare(item, draft, await self._locked(actor, item))
        return result

    async def _candidates(
        self, access: _EdpAccess, item: BoughtItem, part_id: int | None
    ) -> list[EdpPart]:
        if part_id is not None or item.edp_part_id is not None:
            chosen = part_id if part_id is not None else item.edp_part_id
            assert chosen is not None
            return await access.client.get_parts([chosen])
        numbers = [n for n in (item.order_code_1, item.order_code_2) if n]
        ids: list[int] = []
        for match in await access.client.check_numbers(numbers):
            if match.part_ids:
                ids = list(match.part_ids)
                break
        parts = await access.client.get_parts(ids) if ids else []
        return _same_maker(parts, await self._suppliers.get_by_id(item.manufacturer_id))

    async def _locked(self, actor: User, item: BoughtItem) -> set[str]:
        pdm = await self._settings.get_pdm()
        enforce = is_pdm_enabled(pdm) and pdm.cad_items_read_only and not actor.is_systemuser
        return set(
            pdm_locked_fields(kind="bought", enforce=enforce, item_data_source=item.data_source)
        )

    async def _compare(
        self, item: BoughtItem, draft: EdpItemDraft, locked: set[str]
    ) -> list[EdpLookupFieldResult]:
        supplier = (
            await self._suppliers.get_by_id(draft.manufacturer_id)
            if draft.manufacturer_id is not None
            else None
        )
        rows: list[tuple[EdpLookupField, str | None, str | None]] = [
            ("article_name", item.article_name, draft.article_name),
            ("order_code_1", item.order_code_1, draft.order_code_1),
            ("order_code_2", item.order_code_2, draft.order_code_2),
            ("ean", item.ean, draft.ean),
            ("weblink", item.weblink, draft.weblink),
            ("manufacturer_id", item.manufacturer_name, supplier.name if supplier else None),
            (
                "product_family_id",
                item.product_family.name if item.product_family else None,
                draft.product_family_name if draft.product_family_id is not None else None,
            ),
        ]
        fields: list[EdpLookupFieldResult] = []
        for name, current, portal in rows:
            differs = portal is not None and norm(portal) != norm(current)
            fields.append(
                EdpLookupFieldResult(
                    field=name,
                    item_value=current,
                    portal_value=portal,
                    differs=differs,
                    applicable=differs and name not in locked,
                )
            )
        return fields


class ApplyEdpLookup(_EdpUseCase):
    def __init__(
        self,
        bought_item_repo: IBoughtItemCadStore,
        supplier_repo: ISupplierQueries,
        product_family_repo: IProductFamilyQueries,
        settings_repo: IExternalDataSettingsRepository,
        portal_factory: IEplanDataPortalFactory,
        *,
        update_item: UpdateBoughtItem,
        event_bus: IEventBus,
        uow: IUnitOfWork,
    ) -> None:
        super().__init__(
            bought_item_repo, supplier_repo, product_family_repo, settings_repo, portal_factory
        )
        self._update_item = update_item
        self._bus = event_bus
        self._uow = uow

    async def execute(
        self, actor: User, item_id: int, cmd: ApplyEdpLookupCommand
    ) -> BoughtItemResult:
        BoughtItemCatalogueRules.assert_can_update(actor)
        item = await self._item(item_id)
        access = await self._access()
        parts = await access.client.get_parts([cmd.part_id])
        if not parts:
            raise EdpPartNotFoundError(f"EPLAN Data Portal part #{cmd.part_id} not found.")
        draft = await access.builder.draft(parts[0])

        if cmd.fields:
            await self._update_item.execute(actor, item.id, self._update_command(item, draft, cmd))
        saved = await link_edp_part(self._items, self._bus, actor, item.id, cmd.part_id)
        await self._uow.commit()
        return BoughtItemMapper.to_result(saved)

    @staticmethod
    def _update_command(
        item: BoughtItem, draft: EdpItemDraft, cmd: ApplyEdpLookupCommand
    ) -> UpdateBoughtItemCommand:
        """The item as it is, with the chosen fields taken from the portal
        where the portal has a value."""
        chosen = set(cmd.fields)

        def pick(field: EdpLookupField, current: str | None, portal: str | None) -> str | None:
            return portal if field in chosen and portal is not None else current

        manufacturer_id = item.manufacturer_id
        if "manufacturer_id" in chosen and draft.manufacturer_id is not None:
            manufacturer_id = draft.manufacturer_id
        product_family_id = item.product_family_id
        if "product_family_id" in chosen and draft.product_family_id is not None:
            product_family_id = draft.product_family_id
        return UpdateBoughtItemCommand(
            order_code_1=pick("order_code_1", item.order_code_1, draft.order_code_1) or "",
            order_code_2=pick("order_code_2", item.order_code_2, draft.order_code_2),
            gtin=item.gtin,
            ean=pick("ean", item.ean, draft.ean),
            tariff_number=item.tariff_number,
            article_name=pick("article_name", item.article_name, draft.article_name) or "",
            article_group_ids=list(item.article_group_ids),
            status=item.status,
            part_number=item.part_number,
            mass=item.mass,
            note=item.note,
            weblink=pick("weblink", item.weblink, draft.weblink),
            manufacturer_id=manufacturer_id,
            product_family_id=product_family_id,
            successor_item_id=item.successor_item_id,
        )
