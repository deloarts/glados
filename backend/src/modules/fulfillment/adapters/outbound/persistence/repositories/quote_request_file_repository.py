"""SQLAlchemy repositories for the offer documents of a quote request's
supplier entry, a thin subclass of the shared item file repository, and the
lookup of a supplier entry on its own."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_file_model import (
    QuoteRequestFileOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestSupplierOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository._mappers import (
    supplier_orm_to_entity,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository._mappers import (
    supplier_row_load_options,
)
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestSupplier
from src.modules.fulfillment.domain.entities.quote_request_file import QuoteRequestFile
from src.modules.fulfillment.domain.value_objects.quote_file_category import QuoteFileCategory
from src.modules.platform.adapters.outbound.persistence.item_file_repository import (
    SqlAlchemyItemFileRepository,
)


class SqlAlchemyQuoteRequestFileRepository(SqlAlchemyItemFileRepository[QuoteRequestFile]):
    _model = QuoteRequestFileOrmModel
    _entity_cls = QuoteRequestFile
    _category_cls = QuoteFileCategory
    _fk_field = "supplier_row_id"


class SqlAlchemyQuoteRequestSupplierRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> QuoteRequestSupplier | None:
        orm = await self._db.scalar(
            select(QuoteRequestSupplierOrmModel)
            .where(QuoteRequestSupplierOrmModel.id == id)
            .options(*supplier_row_load_options())
        )
        return supplier_orm_to_entity(orm) if orm else None
