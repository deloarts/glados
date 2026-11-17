"""
Concrete implementation of IBoughtItemDemandBucketRepository, a thin subclass of
the shared demand bucket repository.
"""

from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_bucket_model import (
    BoughtItemDemandBucketOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.demand_bucket_repository import (
    DemandBucketRepositoryBase,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_bucket import BoughtItemDemandBucket
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_bucket_repository import (
    IBoughtItemDemandBucketRepository,
)


class SqlAlchemyBoughtItemDemandBucketRepository(
    DemandBucketRepositoryBase[BoughtItemDemandBucket], IBoughtItemDemandBucketRepository
):
    """Implements IBoughtItemDemandBucketRepository."""

    _model = BoughtItemDemandBucketOrmModel
    _entity_cls = BoughtItemDemandBucket
    _demand_model = BoughtItemDemandItemOrmModel
