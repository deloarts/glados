"""
Concrete SQLAlchemy implementations for the MadeItemDemandItem and
MadeItemDemandAllocation aggregates, split one module per aggregate.
Re-exported here so imports of
`...repositories.made_item_demand_repository.SqlAlchemy...` work.
"""

from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.allocation import (
    SqlAlchemyMadeItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.demand_item import (
    SqlAlchemyMadeItemDemandItemRepository,
)

__all__ = [
    "SqlAlchemyMadeItemAllocationRepository",
    "SqlAlchemyMadeItemDemandItemRepository",
]
