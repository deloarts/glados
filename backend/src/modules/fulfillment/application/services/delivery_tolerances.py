"""
Reads the delivery tolerance that applies to an order line: the line's
catalogue item's own values where it has them, else the order settings'
(domain/services/delivery_tolerance.py). The settings are read once per
instance, which lives for one request.
"""

from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISourceItemQueries
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.services.delivery_tolerance import NO_TOLERANCE
from src.modules.fulfillment.domain.services.delivery_tolerance import DeliveryTolerance
from src.modules.fulfillment.domain.services.delivery_tolerance import takes_tolerance
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)


class DeliveryTolerances:
    def __init__(
        self,
        settings_repo: IFulfillmentSettingsRepository,
        bought_item_repo: IBoughtItemQueries,
        source_item_repo: ISourceItemQueries,
    ) -> None:
        self._settings_repo = settings_repo
        self._bought_items = bought_item_repo
        self._source_items = source_item_repo
        self._settings: AdminOrderSettings | None = None

    async def for_line(self, line: OrderItem) -> DeliveryTolerance:
        if not takes_tolerance(line):
            return NO_TOLERANCE
        if self._settings is None:
            self._settings = await self._settings_repo.get_orders()
        item_over, item_under = await self._item_tolerances(line)
        return DeliveryTolerance.resolve(
            over_percent=self._settings.over_delivery_tolerance_percent,
            under_percent=self._settings.under_delivery_tolerance_percent,
            item_over_percent=item_over,
            item_under_percent=item_under,
        )

    async def _item_tolerances(self, line: OrderItem) -> tuple[float | None, float | None]:
        if line.line_type == OrderLineType.BOUGHT and line.bought_item_id is not None:
            bought = await self._bought_items.get_by_id(line.bought_item_id)
            if bought is not None:
                return (
                    bought.over_delivery_tolerance_percent,
                    bought.under_delivery_tolerance_percent,
                )
        if line.line_type == OrderLineType.SOURCE and line.source_item_id is not None:
            source = await self._source_items.get_by_id(line.source_item_id)
            if source is not None:
                return (
                    source.over_delivery_tolerance_percent,
                    source.under_delivery_tolerance_percent,
                )
        return None, None
