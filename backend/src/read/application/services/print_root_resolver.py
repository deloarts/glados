"""
Resolves a (root_type, root_id) pair to the *Result DTO a print template
renders from. Sits on existing repos + mappers directly rather than the
full Get* use cases (e.g. GetProductionOrder's SchedulingRepos); a print
preview needs the same read the API already exposes, not the extra
scheduling context those use cases assemble for their own endpoints.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from src.modules.catalogue.application.mappers.bought_item_mapper import BoughtItemMapper
from src.modules.catalogue.application.mappers.made_item_mapper import MadeItemMapper
from src.modules.catalogue.application.mappers.source_item_mapper import SourceItemMapper
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IMadeItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISourceItemQueries
from src.modules.fulfillment.api import IFulfillmentSettingsRepository
from src.modules.fulfillment.application.dto.production_lot_dto import ScrapTagResult
from src.modules.fulfillment.application.mappers.order_mapper import OrderItemMapper
from src.modules.fulfillment.application.mappers.order_mapper import OrderMapper
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotMapper
from src.modules.fulfillment.application.mappers.production_order_mapper import (
    ProductionOrderMapper,
)
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.value_objects.lot_origin_disposition import LotOriginDisposition
from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome
from src.modules.fulfillment.ports.outbound.fulfillment_queries import IOrderItemDeliveryQueries
from src.modules.fulfillment.ports.outbound.fulfillment_queries import IOrderItemQueries
from src.modules.fulfillment.ports.outbound.fulfillment_queries import IOrderQueries
from src.modules.fulfillment.ports.outbound.fulfillment_queries import IProductionLotQueries
from src.modules.fulfillment.ports.outbound.fulfillment_queries import IProductionOrderQueries
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.quality.domain.value_objects.print_classifier import PrintRootType
from src.shared_kernel.domain.services.clock import as_utc


class PrintRootResolver:
    def __init__(
        self,
        order_repo: IOrderQueries,
        order_item_repo: IOrderItemQueries,
        production_order_repo: IProductionOrderQueries,
        production_lot_repo: IProductionLotQueries,
        made_item_repo: IMadeItemQueries,
        bought_item_repo: IBoughtItemQueries,
        source_item_repo: ISourceItemQueries,
        # Optional, like every other narrowly-scoped addition to this
        # constructor: None only in a caller/test that never resolves the
        # order_item_delivery root type (see resolve() below).
        order_item_delivery_repo: IOrderItemDeliveryQueries | None = None,
        # Gives the tenant's timezone, whose day a scrap tag prints; without
        # it (unit tests) the day is UTC's.
        settings_repo: IFulfillmentSettingsRepository | None = None,
    ) -> None:
        self._orders = order_repo
        self._order_items = order_item_repo
        self._production_orders = production_order_repo
        self._production_lots = production_lot_repo
        self._made_items = made_item_repo
        self._bought_items = bought_item_repo
        self._source_items = source_item_repo
        self._order_item_deliveries = order_item_delivery_repo
        self._settings = settings_repo

    async def _resolve_order(self, root_id: int) -> BaseModel | None:
        purchase_order = await self._orders.get_by_id(root_id)
        if purchase_order is None:
            return None
        # The order docket repeats over the positions, so unlike every
        # other root this one is only useful with its children loaded;
        # OrderMapper sorts them by position.
        return OrderMapper.to_result(
            purchase_order, await self._order_items.get_by_order_id(root_id)
        )

    async def _resolve_order_item(self, root_id: int) -> BaseModel | None:
        item = await self._order_items.get_by_id(root_id)
        return OrderItemMapper.to_result(item) if item else None

    async def _resolve_production_order(self, root_id: int) -> BaseModel | None:
        order = await self._production_orders.get_by_id(root_id)
        return ProductionOrderMapper.to_result(order) if order else None

    async def _resolve_production_lot(self, root_id: int) -> BaseModel | None:
        lot = await self._production_lots.get_by_id(root_id)
        return LotMapper.to_result(lot) if lot else None

    async def _resolve_made_item(self, root_id: int) -> BaseModel | None:
        made_item = await self._made_items.get_by_id(root_id)
        return MadeItemMapper.to_result(made_item) if made_item else None

    async def _resolve_bought_item(self, root_id: int) -> BaseModel | None:
        bought_item = await self._bought_items.get_by_id(root_id)
        return BoughtItemMapper.to_result(bought_item) if bought_item else None

    async def _resolve_source_item(self, root_id: int) -> BaseModel | None:
        source_item = await self._source_items.get_by_id(root_id)
        return SourceItemMapper.to_result(source_item) if source_item else None

    async def _resolve_production_order_completion(self, root_id: int) -> BaseModel | None:
        completion = await self._production_orders.get_completion_by_id(root_id)
        return await self._scrap_tag_from_completion(completion) if completion else None

    async def _resolve_order_item_delivery(self, root_id: int) -> BaseModel | None:
        if self._order_item_deliveries is None:
            return None
        delivery = await self._order_item_deliveries.get_by_id(root_id)
        return await self._scrap_tag_from_delivery(delivery) if delivery else None

    def _resolvers(self) -> dict[str, Callable[[int], Awaitable[BaseModel | None]]]:
        return {
            PrintRootType.ORDER.value: self._resolve_order,
            PrintRootType.ORDER_ITEM.value: self._resolve_order_item,
            PrintRootType.PRODUCTION_ORDER.value: self._resolve_production_order,
            PrintRootType.PRODUCTION_LOT.value: self._resolve_production_lot,
            PrintRootType.MADE_ITEM.value: self._resolve_made_item,
            PrintRootType.BOUGHT_ITEM.value: self._resolve_bought_item,
            PrintRootType.SOURCE_ITEM.value: self._resolve_source_item,
            PrintRootType.PRODUCTION_ORDER_COMPLETION.value: (
                self._resolve_production_order_completion
            ),
            PrintRootType.ORDER_ITEM_DELIVERY.value: self._resolve_order_item_delivery,
        }

    async def resolve(self, root_type: str, root_id: int) -> BaseModel | None:
        handler = self._resolvers().get(root_type)
        return await handler(root_id) if handler else None

    async def _scrap_tag_from_completion(
        self, completion: ProductionOrderCompletion
    ) -> ScrapTagResult | None:
        """None whenever the completion does not actually carry a scrap
        disposition (e.g. an ordinary or QA-accepted completion); the
        scrap_tag classifier has nothing to print from it."""
        if completion.quantity_scrap <= 0:
            return None
        order = await self._production_orders.get_by_id(completion.production_order_id)
        if order is None:
            return None
        lot = await self._lot_for_position(order.lot_position_id)
        if lot is None:
            return None
        reason = completion.scrap_reason.value if completion.scrap_reason is not None else ""
        return ScrapTagResult(
            id=completion.id,
            public_id=completion.public_id,
            quantity=completion.quantity_scrap,
            reason=reason,
            reason_label=_humanize_reason(reason),
            scrap_date=completion.completion_date,
            operator_full_name=completion.operator.full_name if completion.operator else "",
            **_lot_fields(lot),
            **await self._replacement_lot_fields(lot, completion.created),
        )

    async def _scrap_tag_from_delivery(self, delivery: OrderItemDelivery) -> ScrapTagResult | None:
        """None for a delivery that rejected nothing, or whose rejection was
        booked as `redeliver`; only a `lost` rejection ever removed
        pieces from a lot, `redeliver` leaves the lot untouched."""
        if delivery.quantity_rejected <= 0 or delivery.rejection_outcome != RejectionOutcome.LOST:
            return None
        zone = await tenant_zone(self._settings) if self._settings is not None else UTC
        item = await self._order_items.get_by_id(delivery.order_item_id)
        if item is None:
            return None
        lot = await self._lot_for_position(item.lot_position_id)
        if lot is None:
            return None
        return ScrapTagResult(
            id=delivery.id,
            public_id=delivery.public_id,
            quantity=delivery.quantity_rejected,
            reason=delivery.rejection_reason or "",
            reason_label=_humanize_reason(delivery.rejection_reason),
            scrap_date=as_utc(delivery.delivery_date).astimezone(zone).date(),
            operator_full_name=delivery.receiver.full_name if delivery.receiver else "",
            **_lot_fields(lot),
            **await self._replacement_lot_fields(lot, delivery.created),
        )

    async def _lot_for_position(self, lot_position_id: int | None) -> ProductionLot | None:
        if lot_position_id is None:
            return None
        position = await self._production_lots.get_position_by_id(lot_position_id)
        if position is None:
            return None
        return await self._production_lots.get_by_id(position.lot_id)

    async def _replacement_lot_fields(self, lot: ProductionLot, since: datetime) -> dict[str, Any]:
        """The replacement lot spawned FOR THIS occurrence, not just any of
        the lot's replacement lots; a lot can be scrapped more than once.
        Dispositions against one lot are serialized by its own row lock
        (see LotRules/apply_disposition), so a scrap record's own
        replacement lot, if any, is always the earliest replacement lot
        created at or after that record's own `created` timestamp; no
        other scrap record's replacement lot can land in between, because
        the next disposition against this lot cannot start until this
        one's whole transaction, replacement lot included, has committed."""
        replacement_ids = [
            f.id
            for f in lot.follow_up_lots
            if f.disposition == LotOriginDisposition.REPLACEMENT.value
        ]
        if not replacement_ids:
            return {"replacement_lot_id": None, "replacement_lot_number": ""}
        candidates = [
            c for c in await self._production_lots.get_by_ids(replacement_ids) if c.created >= since
        ]
        if not candidates:
            return {"replacement_lot_id": None, "replacement_lot_number": ""}
        earliest = min(candidates, key=lambda c: c.created)
        return {"replacement_lot_id": earliest.id, "replacement_lot_number": earliest.lot_number}


def _lot_fields(lot: ProductionLot) -> dict[str, Any]:
    return {
        "lot_id": lot.id,
        "lot_public_id": lot.public_id,
        "lot_number": lot.lot_number,
        "made_item_id": lot.made_item_id,
        "made_item_label": _made_item_label(lot),
    }


def _made_item_label(lot: ProductionLot) -> str:
    label = lot.made_item_part_number
    if lot.made_item_revision:
        label = f"{label} rev {lot.made_item_revision}"
    return f"{label} - {lot.made_item_article_name}" if lot.made_item_article_name else label


def _humanize_reason(reason: str | None) -> str:
    """A plain, non-localized rendering of a ScrapReason value for the
    printed tag (e.g. "tool_breakage" -> "Tool breakage"); this codebase
    has no backend-side i18n, the frontend's own reason labels are for the
    UI only, not for a physical label rendered server-side."""
    if not reason:
        return ""
    return reason.replace("_", " ").capitalize()
