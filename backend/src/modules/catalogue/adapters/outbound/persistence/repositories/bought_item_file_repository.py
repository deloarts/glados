"""SQLAlchemy repository for files attached to a bought item, a thin subclass of the
shared item file repository."""

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_file_model import (
    BoughtItemFileOrmModel,
)
from src.modules.catalogue.domain.entities.bought_item_file import BoughtItemFile
from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)
from src.modules.platform.adapters.outbound.persistence.item_file_repository import (
    SqlAlchemyItemFileRepository,
)


class SqlAlchemyBoughtItemFileRepository(SqlAlchemyItemFileRepository[BoughtItemFile]):
    _model = BoughtItemFileOrmModel
    _entity_cls = BoughtItemFile
    _category_cls = BoughtItemFileCategory
    _fk_field = "bought_item_id"
