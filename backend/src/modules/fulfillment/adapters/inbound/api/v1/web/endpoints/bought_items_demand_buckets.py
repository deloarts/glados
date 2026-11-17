"""
Bought-item demand bucket endpoints. A bucket is shared team display
state for triaging bought-item demands (see DemandBucketRules),
filtering/sorting/grouping only, never a business-logic input.
Registered as a sibling of bought_items_demand.py (like
bought_items_allocations.py), not nested under it, since nesting under
`/bought-items-demands/` would collide with that router's `/{demand_id}`
int path routes.
"""

from src.modules.fulfillment.adapters.inbound.api.deps.bought_item_demand_buckets import DEPS
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints._demand_bucket_router import (
    DemandBucketEndpointConfig,
)
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints._demand_bucket_router import (
    build_demand_bucket_router,
)
from src.modules.fulfillment.application.dto.bought_item_demand_bucket_dto import (
    CreateBoughtItemDemandBucketCommand,
)
from src.modules.fulfillment.application.dto.bought_item_demand_bucket_dto import (
    UpdateBoughtItemDemandBucketCommand,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_bucket_repository import (
    BoughtItemDemandBucketFilterDto,
)

router = build_demand_bucket_router(
    DemandBucketEndpointConfig(
        filter_dto=BoughtItemDemandBucketFilterDto,
        create_command=CreateBoughtItemDemandBucketCommand,
        update_command=UpdateBoughtItemDemandBucketCommand,
        deps=DEPS,
    )
)
