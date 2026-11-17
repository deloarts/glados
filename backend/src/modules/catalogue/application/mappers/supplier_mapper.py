"""
Converts between Supplier domain entity and DTOs.
"""

from src.modules.catalogue.application.dto.supplier_dto import SupplierResult
from src.modules.catalogue.application.mappers.article_group_mapper import ArticleGroupMapper
from src.modules.catalogue.application.mappers.fabrication_method_mapper import (
    FabricationMethodMapper,
)
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.platform.application.mappers.user_mapper import UserMapper


class SupplierMapper:
    @staticmethod
    def to_result(entity: Supplier) -> SupplierResult:
        return SupplierResult(
            id=entity.id,
            edit_version=entity.edit_version,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            archived=entity.archived,
            name=entity.name,
            legal_name=entity.legal_name,
            vat_id=entity.vat_id,
            level=entity.level,
            external_lead_time_days=entity.external_lead_time_days,
            edp_code=entity.edp_code,
            edp_type_number_first=entity.edp_type_number_first,
            capability_ids=entity.capability_ids,
            capabilities=[FabricationMethodMapper.to_result(c) for c in entity.capabilities],
            article_group_ids=entity.article_group_ids,
            article_groups=[ArticleGroupMapper.to_result(g) for g in entity.article_groups],
            street=entity.street,
            city=entity.city,
            country=entity.country,
            postal_code=entity.postal_code,
            email=entity.email,
            phone=entity.phone,
            weblink=entity.weblink,
            order_email=entity.order_email,
            order_language=entity.order_language,
            order_template=entity.order_template,
            request_email=entity.request_email,
            request_language=entity.request_language,
            request_template=entity.request_template,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
        )
