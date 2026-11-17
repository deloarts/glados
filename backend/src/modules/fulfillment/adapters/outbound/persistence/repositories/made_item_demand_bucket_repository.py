"""
Concrete implementation of IMadeItemDemandBucketRepository, a thin subclass of
the shared demand bucket repository.
"""

from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_bucket_model import (
    MadeItemDemandBucketOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
    MadeItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.demand_bucket_repository import (
    DemandBucketRepositoryBase,
)
from src.modules.fulfillment.domain.entities.made_item_demand_bucket import MadeItemDemandBucket
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_bucket_repository import (
    IMadeItemDemandBucketRepository,
)


class SqlAlchemyMadeItemDemandBucketRepository(
    DemandBucketRepositoryBase[MadeItemDemandBucket], IMadeItemDemandBucketRepository
):
    """Implements IMadeItemDemandBucketRepository."""

    _model = MadeItemDemandBucketOrmModel
    _entity_cls = MadeItemDemandBucket
    _demand_model = MadeItemDemandItemOrmModel
