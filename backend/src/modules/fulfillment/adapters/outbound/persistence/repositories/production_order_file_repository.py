"""SQLAlchemy repository for files attached to a production order, a thin subclass of the
shared item file repository."""

from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_file_model import (
    ProductionOrderFileOrmModel,
)
from src.modules.fulfillment.domain.entities.production_order_file import ProductionOrderFile
from src.modules.fulfillment.domain.value_objects.production_order_file_category import (
    ProductionOrderFileCategory,
)
from src.modules.platform.adapters.outbound.persistence.item_file_repository import (
    SqlAlchemyItemFileRepository,
)


class SqlAlchemyProductionOrderFileRepository(SqlAlchemyItemFileRepository[ProductionOrderFile]):
    _model = ProductionOrderFileOrmModel
    _entity_cls = ProductionOrderFile
    _category_cls = ProductionOrderFileCategory
    _fk_field = "production_order_id"
