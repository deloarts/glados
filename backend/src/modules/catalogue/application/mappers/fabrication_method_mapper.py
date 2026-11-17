"""
Converts between FabricationMethod domain entity and DTOs.
"""

from src.modules.catalogue.application.dto.fabrication_method_dto import FabricationMethodResult
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.platform.application.mappers.user_mapper import UserMapper


class FabricationMethodMapper:
    @staticmethod
    def to_result(entity: FabricationMethod) -> FabricationMethodResult:
        return FabricationMethodResult(
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
            requires_machine=entity.requires_machine,
            required_external=entity.required_external,
            default_supplier_id=entity.default_supplier_id,
            lead_time_days=entity.lead_time_days,
            default_for_assemblies=entity.default_for_assemblies,
            archived=entity.archived,
        )
