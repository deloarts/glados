"""
Row mapping and load options of the demand items of bought items.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.mappers.bought_item_mappers import (
    item_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.models.article_group_model import (
    ArticleGroupOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus


# Every relationship demand_orm_to_entity reads. The item paths mirror
# bought_item_load_options(), since the demand embeds the full bought item.
@lru_cache(maxsize=1)
def bought_item_demand_load_options() -> tuple[ORMOption, ...]:
    return (
        load_user(BoughtItemDemandItemOrmModel.creator),
        load_user(BoughtItemDemandItemOrmModel.changed_by),
        selectinload(BoughtItemDemandItemOrmModel.project).selectinload(ProjectOrmModel.customer),
        load_user(BoughtItemDemandItemOrmModel.item, BoughtItemOrmModel.creator),
        load_user(BoughtItemDemandItemOrmModel.item, BoughtItemOrmModel.changed_by),
        selectinload(BoughtItemDemandItemOrmModel.item).selectinload(
            BoughtItemOrmModel.manufacturer
        ),
        selectinload(BoughtItemDemandItemOrmModel.item).selectinload(
            BoughtItemOrmModel.product_family
        ),
        load_user(
            BoughtItemDemandItemOrmModel.item,
            BoughtItemOrmModel.article_groups,
            ArticleGroupOrmModel.creator,
        ),
        load_user(
            BoughtItemDemandItemOrmModel.item,
            BoughtItemOrmModel.article_groups,
            ArticleGroupOrmModel.changed_by,
        ),
    )


def demand_orm_to_entity(orm: BoughtItemDemandItemOrmModel) -> BoughtItemDemandItem:
    return BoughtItemDemandItem(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        changed=utc_aware(orm.changed),
        changes=list(orm.changes or []),
        status=BoughtItemDemandStatus(orm.status),
        quantity=orm.quantity,
        unit=orm.unit,
        items_per_unit=orm.items_per_unit,
        high_priority=orm.high_priority,
        notify_on_delivery=orm.notify_on_delivery,
        note=orm.note,
        desired_delivery_date=orm.desired_delivery_date,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        item_id=orm.item_id,
        project_id=orm.project_id,
        bucket_id=orm.bucket_id,
        canceled_at=orm.canceled_at,
        fulfilled_manually_at=orm.fulfilled_manually_at,
        item_order_code_1=orm.item.order_code_1 if orm.item else "",
        item_article_name=orm.item.article_name if orm.item else "",
        project_number=orm.project.project_number if orm.project else "",
        project_customer=orm.project.customer.name
        if (orm.project and orm.project.customer)
        else "",
        project_description=(orm.project.description or "") if orm.project else "",
        project_status=ProjectStatus(orm.project.status) if orm.project else ProjectStatus.ARCHIVED,
        item=item_orm_to_entity(orm.item) if orm.item else None,
    )


def demand_entity_to_dict(d: BoughtItemDemandItem) -> dict[str, Any]:
    return {
        "created": d.created,
        "changed": d.changed,
        "changes": d.changes,
        "status": d.status.value,
        "quantity": d.quantity,
        "unit": d.unit,
        "items_per_unit": d.items_per_unit,
        "high_priority": d.high_priority,
        "notify_on_delivery": d.notify_on_delivery,
        "note": d.note,
        "desired_delivery_date": d.desired_delivery_date,
        "creator_id": d.creator_id,
        "item_id": d.item_id,
        "project_id": d.project_id,
        "bucket_id": d.bucket_id,
        "canceled_at": d.canceled_at,
        "fulfilled_manually_at": d.fulfilled_manually_at,
    }
