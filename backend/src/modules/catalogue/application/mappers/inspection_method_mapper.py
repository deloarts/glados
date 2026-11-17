"""
Converts between InspectionMethod domain entity and DTOs.
"""

from src.modules.catalogue.application.dto.inspection_method_dto import InspectionMethodResult
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.platform.application.mappers.user_mapper import UserMapper


class InspectionMethodMapper:
    @staticmethod
    def to_result(entity: InspectionMethod) -> InspectionMethodResult:
        return InspectionMethodResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            sort_order=entity.sort_order,
            name=entity.name.as_dict(),
            label_color=entity.label_color,
            label_font_color=entity.label_font_color,
            description=entity.description.as_dict(),
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
            default_setup_minutes=entity.default_setup_minutes,
            default_minutes_per_piece=entity.default_minutes_per_piece,
            requires_evidence=entity.requires_evidence,
            archived=entity.archived,
            default_machine_id=entity.default_machine_id,
            default_machine_name=entity.default_machine_name,
        )
