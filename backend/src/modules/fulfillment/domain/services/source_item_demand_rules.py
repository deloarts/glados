"""
The rule that decides whether a source item demand's quantity may still be
edited: only while it is OPEN and not canceled, since once it is allocated
the order line is the source of truth for its quantity. A direct edit of the
demand and a DRAFT lot's quantity edit, which resizes the lot's raw material
demand, share it, so both refuse alike.
"""

from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.errors import SourceItemDemandAlreadyCanceledError
from src.modules.fulfillment.domain.errors import SourceItemDemandAlreadyOrderedError
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)


def assert_source_demand_editable(demand: SourceItemDemandItem) -> None:
    """Raises unless the demand is OPEN and not canceled."""
    if demand.canceled_at is not None:
        raise SourceItemDemandAlreadyCanceledError(
            f"Source item demand #{demand.id} is canceled and cannot be updated."
        )
    if demand.status != SourceItemDemandStatus.OPEN:
        raise SourceItemDemandAlreadyOrderedError(
            f"Source item demand #{demand.id} is already allocated and cannot "
            "be edited, cancel and recreate it instead."
        )
