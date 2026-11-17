"""
Re-exported so imports of
`...repositories.production_lot_repository.SqlAlchemyProductionLotRepository` work.
"""

from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)

__all__ = [
    "SqlAlchemyProductionLotRepository",
]
