"""
Concrete SQLAlchemy implementation for the MadeItem catalogue aggregate.
Re-exported here so imports of
`...repositories.made_item_repository.SqlAlchemyMadeItemRepository` work.
"""

from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)

__all__ = [
    "SqlAlchemyMadeItemRepository",
]
