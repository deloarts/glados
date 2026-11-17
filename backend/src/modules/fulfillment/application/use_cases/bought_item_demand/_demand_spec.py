"""
Binds the bought item demand types to the demand use cases the three
families share in src/modules/fulfillment/application/use_cases/_demand_family/.
"""

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.fulfillment.application.dto.bought_item_demand_dto import DemandItemResult
from src.modules.fulfillment.application.mappers.bought_item_demand_mapper import (
    BoughtItemDemandItemMapper,
)
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandFamilySpec
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.services.allocation_service import BoughtItemAllocationRules
from src.modules.fulfillment.domain.services.lifecycle.demand import BOUGHT_FILL_RANK
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate

SPEC: DemandFamilySpec[BoughtItemDemandItem, DemandItemResult] = DemandFamilySpec(
    rules=BoughtItemAllocationRules,
    aggregate=LifecycleAggregate.BOUGHT_DEMANDS,
    to_result=BoughtItemDemandItemMapper.to_result,
    log_noun="demand",
    stock_source=AllocationSource.STOCK,
    fill_rank=BOUGHT_FILL_RANK,
)
