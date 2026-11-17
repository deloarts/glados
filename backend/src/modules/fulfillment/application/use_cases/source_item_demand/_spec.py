"""
Binds the source item demand types to the demand use cases the three
families share in src/modules/fulfillment/application/use_cases/_demand_family/.
"""

from src.modules.fulfillment.application.dto.source_item_demand_dto import SourceItemDemandResult
from src.modules.fulfillment.application.mappers.source_item_demand_mapper import (
    SourceItemDemandMapper,
)
from src.modules.fulfillment.application.use_cases._demand_family.spec import DemandFamilySpec
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.services.lifecycle.demand import SOURCE_FILL_RANK
from src.modules.fulfillment.domain.services.source_item_allocation_service import (
    SourceItemAllocationRules,
)
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemAllocationSource,
)

SPEC: DemandFamilySpec[SourceItemDemandItem, SourceItemDemandResult] = DemandFamilySpec(
    rules=SourceItemAllocationRules,
    aggregate=LifecycleAggregate.SOURCE_DEMANDS,
    to_result=SourceItemDemandMapper.to_result,
    log_noun="source item demand",
    stock_source=SourceItemAllocationSource.STOCK,
    fill_rank=SOURCE_FILL_RANK,
)
