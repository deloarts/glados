"""Converts between MadeItemDemandItem domain entity and DTOs, flattening project and item
relationships."""

from src.modules.catalogue.application.mappers.made_item_mapper import MadeItemMapper
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemDemandItemResult
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.platform.application.mappers.user_mapper import UserMapper


class MadeItemDemandItemMapper:
    @staticmethod
    def to_result(entity: MadeItemDemandItem) -> MadeItemDemandItemResult:
        return MadeItemDemandItemResult(
            id=entity.id,
            public_id=entity.public_id,
            status=entity.status,
            created=entity.created,
            changed=entity.changed,
            quantity=entity.quantity,
            unit=entity.unit,
            items_per_unit=entity.items_per_unit,
            high_priority=entity.high_priority,
            notify_on_delivery=entity.notify_on_delivery,
            note=entity.note,
            desired_delivery_date=entity.desired_delivery_date,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
            made_item_id=entity.made_item_id,
            item_part_number=entity.item_part_number,
            item_revision=entity.item_revision,
            item_article_name=entity.item_article_name,
            item=MadeItemMapper.to_result(entity.item) if entity.item else None,
            project_id=entity.project_id,
            project_number=entity.project_number,
            project_customer=entity.project_customer,
            project_description=entity.project_description,
            project_status=entity.project_status,
            is_alteration=entity.is_alteration,
            alteration_of_made_item_id=entity.alteration_of_made_item_id,
            alteration_of_made_item_part_number=entity.alteration_of_made_item_part_number,
            alteration_of_made_item_revision=entity.alteration_of_made_item_revision,
            alteration_of_made_item_article_name=entity.alteration_of_made_item_article_name,
            bucket_id=entity.bucket_id,
            canceled_at=entity.canceled_at,
            fulfilled_manually_at=entity.fulfilled_manually_at,
        )
