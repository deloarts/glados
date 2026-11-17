"""
Shared SourceItemDemandItem construction, used by the manual "Demand Source
Item" flow (CreateSourceItemDemand, caller-supplied quantity/unit/etc.) and
by the auto-creation call sites (CreateLot, SwitchLotMaterialSource, using
the lot's own quantity and sensible defaults), keeps the entity shape in
one place.
"""

from datetime import date

from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


def build_source_item_demand(
    lot: ProductionLot,
    actor: User,
    *,
    quantity: float,
    unit: str,
    items_per_unit: float,
    high_priority: bool,
    notify_on_delivery: bool,
    note: str | None,
    desired_delivery_date: date | None,
) -> SourceItemDemandItem:
    now = now_utc()
    return SourceItemDemandItem(
        id=0,
        created=now,
        changed=now,
        changes=append_changelog(
            [], actor.full_name, f"Source item demand created for lot {lot.lot_number!r}."
        ),
        status=SourceItemDemandStatus.OPEN,
        quantity=quantity,
        unit=unit,
        items_per_unit=items_per_unit,
        high_priority=high_priority,
        notify_on_delivery=notify_on_delivery,
        note=note,
        desired_delivery_date=desired_delivery_date,
        creator_id=actor.id,
        bought_item_id=lot.source_bought_item_id,
        source_item_id=lot.source_item_id,
        lot_id=lot.id,
        project_id=lot.project_id,
    )
