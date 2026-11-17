"""
Converts between ProductFamily domain entity and DTOs.
"""

from src.modules.catalogue.application.dto.product_family_dto import ProductFamilyResult
from src.modules.catalogue.domain.entities.product_family import ProductFamily
from src.modules.platform.application.mappers.user_mapper import UserMapper


class ProductFamilyMapper:
    @staticmethod
    def to_result(entity: ProductFamily) -> ProductFamilyResult:
        return ProductFamilyResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            archived=entity.archived,
            name=entity.name,
            label_color=entity.label_color,
            label_font_color=entity.label_font_color,
            description=entity.description,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
        )
