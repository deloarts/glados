"""SQLAlchemy repository for files attached to a order, a thin subclass of the
shared item file repository that also maps the delivery row a picture
documents."""

from typing import Any

from src.modules.fulfillment.adapters.outbound.persistence.models.order_file_model import (
    OrderFileOrmModel,
)
from src.modules.fulfillment.domain.entities.order_file import OrderFile
from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory
from src.modules.platform.adapters.outbound.persistence.item_file_repository import (
    SqlAlchemyItemFileRepository,
)


class SqlAlchemyOrderFileRepository(SqlAlchemyItemFileRepository[OrderFile]):
    _model = OrderFileOrmModel
    _entity_cls = OrderFile
    _category_cls = OrderFileCategory
    _fk_field = "order_id"

    def _orm_to_entity(self, orm: Any) -> OrderFile:
        entity = super()._orm_to_entity(orm)
        entity.delivery_id = orm.delivery_id
        return entity

    def _new_orm(self, file: OrderFile) -> Any:
        orm = super()._new_orm(file)
        orm.delivery_id = file.delivery_id
        return orm
