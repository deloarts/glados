"""
Concrete implementation of ISourceItemDemandBucketRepository, a thin subclass of
the shared demand bucket repository.
"""

from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_bucket_model import (
    SourceItemDemandBucketOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.demand_bucket_repository import (
    DemandBucketRepositoryBase,
)
from src.modules.fulfillment.domain.entities.source_item_demand_bucket import SourceItemDemandBucket
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_bucket_repository import (
    ISourceItemDemandBucketRepository,
)


class SqlAlchemySourceItemDemandBucketRepository(
    DemandBucketRepositoryBase[SourceItemDemandBucket], ISourceItemDemandBucketRepository
):
    """Implements ISourceItemDemandBucketRepository."""

    _model = SourceItemDemandBucketOrmModel
    _entity_cls = SourceItemDemandBucket
    _demand_model = SourceItemDemandItemOrmModel
