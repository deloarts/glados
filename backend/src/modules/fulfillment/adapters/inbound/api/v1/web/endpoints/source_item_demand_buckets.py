"""
Source-item demand bucket endpoints. A bucket is shared team display
state for triaging source-item demands (see DemandBucketRules),
filtering/sorting/grouping only, never a business-logic input.
Registered as a sibling of source_item_demands.py (like
source_item_allocations.py), not nested under it, since nesting under
`/source-item-demands/` would collide with that router's `/{demand_id}`
int path routes.
"""

from src.modules.fulfillment.adapters.inbound.api.deps.source_item_demand_buckets import DEPS
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints._demand_bucket_router import (
    DemandBucketEndpointConfig,
)
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints._demand_bucket_router import (
    build_demand_bucket_router,
)
from src.modules.fulfillment.application.dto.source_item_demand_bucket_dto import (
    CreateSourceItemDemandBucketCommand,
)
from src.modules.fulfillment.application.dto.source_item_demand_bucket_dto import (
    UpdateSourceItemDemandBucketCommand,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_bucket_repository import (
    SourceItemDemandBucketFilterDto,
)

router = build_demand_bucket_router(
    DemandBucketEndpointConfig(
        filter_dto=SourceItemDemandBucketFilterDto,
        create_command=CreateSourceItemDemandBucketCommand,
        update_command=UpdateSourceItemDemandBucketCommand,
        deps=DEPS,
    )
)
