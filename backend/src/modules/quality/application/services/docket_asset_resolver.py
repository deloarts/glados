"""
Resolves the image-valued computed sources a docket can reference
(@part_image, @company_logo) into real bytes, generic across every root
type a docket classifier can have; see the reachability table in the
printing plan. Company branding needs no root at all; the part photo needs
a root-type-specific hop to an item id and kind. The part photo is the
picture shown for the item everywhere else too (pick_picture), as its
full-size image.

A missing image, a disabled storage backend, or an unset logo must never
fail a print; every method here returns None on any such gap and lets
the renderer's own fallback_text carry the block instead
(docket_renderer.py's _draw_image).
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import date

from pydantic import BaseModel

from src.modules.catalogue.domain.policies.item_picture_selection import pick_picture
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_variant import ItemPictureVariant
from src.modules.catalogue.ports.outbound.catalogue_queries import IItemPictureQueries
from src.modules.fulfillment.api import IFulfillmentSettingsRepository
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.quality.domain.value_objects.print_classifier import PrintRootType
from src.shared_kernel.domain.services.clock import today_in


def _made_item_id_for(root_type: str, root: BaseModel) -> int | None:
    """The made_item_id @part_image resolves through, by root type: the
    made_item_docket root IS the made item, while lot_docket and
    production_order_docket reach one via their made_item_id field."""
    if root_type == PrintRootType.MADE_ITEM.value:
        id_value = getattr(root, "id", None)
        return id_value if isinstance(id_value, int) else None
    if root_type in (PrintRootType.PRODUCTION_LOT.value, PrintRootType.PRODUCTION_ORDER.value):
        made_item_id = getattr(root, "made_item_id", None)
        return made_item_id if isinstance(made_item_id, int) else None
    return None


class DocketAssetResolver:
    def __init__(
        self,
        item_picture_repo: IItemPictureQueries,
        admin_settings_repo: IFulfillmentSettingsRepository,
        storage: IStoragePort | None,
    ) -> None:
        self._pictures = item_picture_repo
        self._admin_settings = admin_settings_repo
        self._storage = storage
        # storage_path -> bytes|None, for the row-image case where one
        # article can appear on many lines of the same order.
        self._downloads: dict[str, bytes | None] = {}

    async def resolve_part_image(self, root_type: str, root: BaseModel) -> bytes | None:
        if root_type == PrintRootType.BOUGHT_ITEM.value:
            item_id = getattr(root, "id", None)
            return await self._bought_item_image(item_id) if isinstance(item_id, int) else None

        if root_type == PrintRootType.SOURCE_ITEM.value:
            item_id = getattr(root, "id", None)
            return await self._source_item_image(item_id) if isinstance(item_id, int) else None

        made_item_id = _made_item_id_for(root_type, root)
        return await self._made_item_image(made_item_id) if made_item_id is not None else None

    async def resolve_row_image(self, row: BaseModel) -> bytes | None:
        """The part photo for ONE table row (@item_image), dispatched on the
        line type the row carries: an order line points at a bought, source
        or made item, or at none of them (a VIRTUAL line), in which case
        there is simply nothing to show.

        Downloads are memoised per resolver instance because a single order
        happily lists the same article on several lines, and each repeat
        would otherwise be another round trip to object storage."""
        resolvers: tuple[tuple[str, Callable[[int], Awaitable[bytes | None]]], ...] = (
            ("bought_item_id", self._bought_item_image),
            ("source_item_id", self._source_item_image),
            ("made_item_id", self._made_item_image),
        )
        for attribute, resolve in resolvers:
            item_id = getattr(row, attribute, None)
            if isinstance(item_id, int):
                return await resolve(item_id)
        return None

    async def _bought_item_image(self, item_id: int) -> bytes | None:
        return await self._item_image(ItemKind.BOUGHT, item_id)

    async def _source_item_image(self, item_id: int) -> bytes | None:
        return await self._item_image(ItemKind.SOURCE, item_id)

    async def _made_item_image(self, item_id: int) -> bytes | None:
        return await self._item_image(ItemKind.MADE, item_id)

    async def _item_image(self, kind: ItemKind, item_id: int) -> bytes | None:
        picture = pick_picture(await self._pictures.get_by_item(kind, item_id))
        blob = picture.blob(ItemPictureVariant.IMAGE) if picture is not None else None
        return await self._download(blob[0]) if blob is not None else None

    async def resolve_company_logo(self) -> bytes | None:
        key = (await self._admin_settings.get_general()).company_logo_key
        return await self._download(key) if key else None

    async def resolve_company_name(self) -> str:
        return (await self._admin_settings.get_general()).company_name or ""

    async def resolve_today(self) -> date:
        """Today in the tenant's timezone, the date a printed @today shows."""
        return today_in(await tenant_zone(self._admin_settings))

    async def _download(self, storage_path: str) -> bytes | None:
        if self._storage is None:
            return None
        if storage_path in self._downloads:
            return self._downloads[storage_path]
        try:
            data, _content_type = await self._storage.download(storage_path)
        except Exception:  # a broken/missing file must not kill a print
            log.warning(
                "Docket asset %r could not be downloaded; printing without it.",
                storage_path,
                exc_info=True,
            )
            data = None
        self._downloads[storage_path] = data
        return data
