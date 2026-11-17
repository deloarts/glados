"""SQLAlchemy repository for files attached to a made item, a thin subclass of the
shared item file repository."""

from src.modules.catalogue.adapters.outbound.persistence.models.made_item_file_model import (
    MadeItemFileOrmModel,
)
from src.modules.catalogue.domain.entities.made_item_file import MadeItemFile
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.modules.platform.adapters.outbound.persistence.item_file_repository import (
    SqlAlchemyItemFileRepository,
)


class SqlAlchemyMadeItemFileRepository(SqlAlchemyItemFileRepository[MadeItemFile]):
    _model = MadeItemFileOrmModel
    _entity_cls = MadeItemFile
    _category_cls = MadeItemFileCategory
    _fk_field = "made_item_id"
