"""
ORM <-> domain entity mapping helpers for the MadeItemDemandItem aggregate.
Not part of the public API of this package.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.mappers.made_item_mappers import (
    item_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.made_item_mappers import (
    made_item_load_options,
)
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
    MadeItemDemandItemOrmModel,
)
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus

# ── DemandItem ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def demand_load_options() -> tuple[ORMOption, ...]:
    """Every relationship demand_orm_to_entity traverses, including the full
    made-item graph it embeds through item_orm_to_entity."""
    return (
        load_user(MadeItemDemandItemOrmModel.creator),
        load_user(MadeItemDemandItemOrmModel.changed_by),
        selectinload(MadeItemDemandItemOrmModel.item).options(*made_item_load_options()),
        selectinload(MadeItemDemandItemOrmModel.alteration_of_made_item),
        selectinload(MadeItemDemandItemOrmModel.project).selectinload(ProjectOrmModel.customer),
    )


def demand_orm_to_entity(orm: MadeItemDemandItemOrmModel) -> MadeItemDemandItem:
    return MadeItemDemandItem(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        changed=utc_aware(orm.changed),
        changes=list(orm.changes or []),
        status=MadeItemDemandStatus(orm.status),
        quantity=orm.quantity,
        unit=orm.unit,
        items_per_unit=orm.items_per_unit,
        high_priority=orm.high_priority,
        notify_on_delivery=orm.notify_on_delivery,
        note=orm.note,
        desired_delivery_date=orm.desired_delivery_date,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        made_item_id=orm.made_item_id,
        project_id=orm.project_id,
        is_alteration=orm.is_alteration,
        alteration_of_made_item_id=orm.alteration_of_made_item_id,
        bucket_id=orm.bucket_id,
        canceled_at=orm.canceled_at,
        fulfilled_manually_at=orm.fulfilled_manually_at,
        item_part_number=(orm.item.part_number or "") if orm.item else "",
        item_revision=orm.item.revision if orm.item else "",
        item_article_name=orm.item.article_name if orm.item else "",
        project_number=orm.project.project_number if orm.project else "",
        project_customer=orm.project.customer.name
        if (orm.project and orm.project.customer)
        else "",
        project_description=(orm.project.description or "") if orm.project else "",
        project_status=ProjectStatus(orm.project.status) if orm.project else ProjectStatus.ARCHIVED,
        item=item_orm_to_entity(orm.item) if orm.item else None,
        alteration_of_made_item_part_number=(
            (orm.alteration_of_made_item.part_number or "") if orm.alteration_of_made_item else ""
        ),
        alteration_of_made_item_revision=(
            orm.alteration_of_made_item.revision if orm.alteration_of_made_item else ""
        ),
        alteration_of_made_item_article_name=(
            orm.alteration_of_made_item.article_name if orm.alteration_of_made_item else ""
        ),
    )


def demand_entity_to_dict(d: MadeItemDemandItem) -> dict[str, Any]:
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
        "made_item_id": d.made_item_id,
        "project_id": d.project_id,
        "is_alteration": d.is_alteration,
        "alteration_of_made_item_id": d.alteration_of_made_item_id,
        "bucket_id": d.bucket_id,
        "canceled_at": d.canceled_at,
        "fulfilled_manually_at": d.fulfilled_manually_at,
    }
