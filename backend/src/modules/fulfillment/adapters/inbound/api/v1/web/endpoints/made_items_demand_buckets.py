"""
Made-item demand bucket endpoints. A bucket is shared team display
state for triaging made-item demands (see DemandBucketRules),
filtering/sorting/grouping only, never a business-logic input.
Registered as a sibling of made_items_demand.py (like
made_items_allocations.py), not nested under it, since nesting under
`/made-items-demands/` would collide with that router's `/{demand_id}`
int path routes.
"""

from src.modules.fulfillment.adapters.inbound.api.deps.made_item_demand_buckets import DEPS
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints._demand_bucket_router import (
    DemandBucketEndpointConfig,
)
from src.modules.fulfillment.adapters.inbound.api.v1.web.endpoints._demand_bucket_router import (
    build_demand_bucket_router,
)
from src.modules.fulfillment.application.dto.made_item_demand_bucket_dto import (
    CreateMadeItemDemandBucketCommand,
)
from src.modules.fulfillment.application.dto.made_item_demand_bucket_dto import (
    UpdateMadeItemDemandBucketCommand,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_bucket_repository import (
    MadeItemDemandBucketFilterDto,
)

router = build_demand_bucket_router(
    DemandBucketEndpointConfig(
        filter_dto=MadeItemDemandBucketFilterDto,
        create_command=CreateMadeItemDemandBucketCommand,
        update_command=UpdateMadeItemDemandBucketCommand,
        deps=DEPS,
    )
)
