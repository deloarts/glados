"""SQLAlchemy repository for files attached to a product, a thin subclass of the
shared item file repository."""

from src.modules.platform.adapters.outbound.persistence.item_file_repository import (
    SqlAlchemyItemFileRepository,
)
from src.modules.workspace.adapters.outbound.persistence.models.product_file_model import (
    ProductFileOrmModel,
)
from src.modules.workspace.domain.entities.product_file import ProductFile
from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory


class SqlAlchemyProductFileRepository(SqlAlchemyItemFileRepository[ProductFile]):
    _model = ProductFileOrmModel
    _entity_cls = ProductFile
    _category_cls = ProductFileCategory
    _fk_field = "product_id"
