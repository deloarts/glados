"""SQLAlchemy repository for files attached to a source item, a thin subclass of the
shared item file repository."""

from src.modules.catalogue.adapters.outbound.persistence.models.source_item_file_model import (
    SourceItemFileOrmModel,
)
from src.modules.catalogue.domain.entities.source_item_file import SourceItemFile
from src.modules.catalogue.domain.value_objects.source_item_file_category import (
    SourceItemFileCategory,
)
from src.modules.platform.adapters.outbound.persistence.item_file_repository import (
    SqlAlchemyItemFileRepository,
)


class SqlAlchemySourceItemFileRepository(SqlAlchemyItemFileRepository[SourceItemFile]):
    _model = SourceItemFileOrmModel
    _entity_cls = SourceItemFile
    _category_cls = SourceItemFileCategory
    _fk_field = "source_item_id"
