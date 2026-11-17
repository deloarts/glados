"""Converts between SourceItem domain entity and DTOs."""

from src.modules.catalogue.application.dto.source_item_dto import SourceItemResult
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.platform.application.mappers.user_mapper import UserMapper


class SourceItemMapper:
    @staticmethod
    def to_result(entity: SourceItem) -> SourceItemResult:
        return SourceItemResult(
            id=entity.id,
            edit_version=entity.edit_version,
            public_id=entity.public_id,
            status=entity.status,
            created=entity.created,
            changed=entity.changed,
            archived=entity.archived,
            type_id=entity.type_id,
            type_name=entity.type_name.as_dict(),
            dimension=entity.dimension,
            material=entity.material,
            mass=entity.mass,
            note=entity.note,
            order_code_1=entity.order_code_1,
            order_code_2=entity.order_code_2,
            successor_item_id=entity.successor_item_id,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
            approver_id=entity.approver_id,
            manufacturer_id=entity.manufacturer_id,
            manufacturer_name=entity.manufacturer_name,
            over_delivery_tolerance_percent=entity.over_delivery_tolerance_percent,
            under_delivery_tolerance_percent=entity.under_delivery_tolerance_percent,
            changes=entity.changes,
        )
