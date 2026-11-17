"""
Binds the made item demand types to the demand use cases the three
families share in src/modules/fulfillment/application/use_cases/_demand_family/.
"""

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemDemandItemResult
from src.modules.fulfillment.application.mappers.made_item_demand_mapper import (
    MadeItemDemandItemMapper,
)
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandFamilySpec
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.services.lifecycle.demand import MADE_FILL_RANK
from src.modules.fulfillment.domain.services.made_item_demand_rules import MadeItemAllocationRules
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate

SPEC: DemandFamilySpec[MadeItemDemandItem, MadeItemDemandItemResult] = DemandFamilySpec(
    rules=MadeItemAllocationRules,
    aggregate=LifecycleAggregate.MADE_DEMANDS,
    to_result=MadeItemDemandItemMapper.to_result,
    log_noun="demand",
    stock_source=MadeItemAllocationSource.STOCK,
    fill_rank=MADE_FILL_RANK,
)
