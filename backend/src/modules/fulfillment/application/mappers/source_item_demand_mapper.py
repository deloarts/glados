"""Converts between SourceItemDemandItem domain entity and DTOs, flattening project and item
relationships."""

from src.modules.catalogue.application.mappers.bought_item_mapper import BoughtItemMapper
from src.modules.catalogue.application.mappers.source_item_mapper import SourceItemMapper
from src.modules.fulfillment.application.dto.source_item_demand_dto import SourceItemDemandResult
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.platform.application.mappers.user_mapper import UserMapper


class SourceItemDemandMapper:
    @staticmethod
    def to_result(entity: SourceItemDemandItem) -> SourceItemDemandResult:
        return SourceItemDemandResult(
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
            bought_item_id=entity.bought_item_id,
            bought_item=BoughtItemMapper.to_result(entity.bought_item)
            if entity.bought_item
            else None,
            source_item_id=entity.source_item_id,
            source_item=SourceItemMapper.to_result(entity.source_item)
            if entity.source_item
            else None,
            lot_id=entity.lot_id,
            lot_number=entity.lot_number,
            project_id=entity.project_id,
            project_number=entity.project_number,
            project_customer=entity.project_customer,
            project_description=entity.project_description,
            project_status=entity.project_status,
            bucket_id=entity.bucket_id,
            canceled_at=entity.canceled_at,
            fulfilled_manually_at=entity.fulfilled_manually_at,
            changes=entity.changes,
        )
