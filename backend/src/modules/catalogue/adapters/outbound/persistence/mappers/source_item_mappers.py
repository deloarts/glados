"""
Row mapping of source items, used by the repository and by other modules'
persistence adapters that load a related row.
"""

from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
    SourceItemOrmModel,
)
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.platform.adapters.outbound.persistence.mapping_common import archived_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.domain.value_objects.localized_text import LocalizedText


def source_item_orm_to_entity(orm: SourceItemOrmModel) -> SourceItem:
    return SourceItem(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        type_id=orm.type_id,
        dimension=orm.dimension,
        material=orm.material,
        mass=orm.mass,
        note=orm.note,
        order_code_1=orm.order_code_1,
        order_code_2=orm.order_code_2,
        status=SourceItemCatalogueStatus(orm.status),
        approver_id=orm.approver_id,
        manufacturer_id=orm.manufacturer_id,
        successor_item_id=orm.successor_item_id,
        over_delivery_tolerance_percent=orm.over_delivery_tolerance_percent,
        under_delivery_tolerance_percent=orm.under_delivery_tolerance_percent,
        manufacturer_name=orm.manufacturer.name if orm.manufacturer else "",
        type_name=LocalizedText(values=dict(orm.type.name or {})) if orm.type else LocalizedText(),
        **archived_kwargs(
            utc_aware(orm.changed),
            orm.changes,
            orm.archived,
        ),
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        edit_version=orm.edit_version,
    )
