"""Use case factories: bought-item demand bucket CRUD."""

from src.modules.fulfillment.adapters.inbound.api.deps.demand_buckets import (
    build_demand_bucket_deps,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_bought_item_demand_bucket_repo,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand_bucket.create_bucket import (
    CreateBucket,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand_bucket.delete_bucket import (
    DeleteBucket,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand_bucket.get_bucket import (
    GetBuckets,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand_bucket.update_bucket import (
    UpdateBucket,
)

DEPS = build_demand_bucket_deps(
    get_bought_item_demand_bucket_repo,
    get_buckets_cls=GetBuckets,
    create_cls=CreateBucket,
    update_cls=UpdateBucket,
    delete_cls=DeleteBucket,
)
