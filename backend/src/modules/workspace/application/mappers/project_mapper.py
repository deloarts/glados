"""
Converts between Project domain entity and DTOs.
"""

from src.modules.catalogue.application.mappers.customer_mapper import CustomerMapper
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.workspace.application.dto.project_dto import ProjectResult
from src.modules.workspace.application.mappers.product_mapper import ProductMapper
from src.modules.workspace.domain.entities.project import Project


class ProjectMapper:
    @staticmethod
    def to_result(entity: Project) -> ProjectResult:
        return ProjectResult(
            id=entity.id,
            public_id=entity.public_id,
            project_number=entity.project_number,
            customer_id=entity.customer_id,
            customer=CustomerMapper.to_result(entity.customer) if entity.customer else None,
            product_id=entity.product_id,
            product=ProductMapper.to_result(entity.product) if entity.product else None,
            description=entity.description,
            status=entity.status,
            designated_user_id=entity.designated_user_id,
            created=entity.created,
            changed=entity.changed,
            changes=entity.changes,
            deleted=entity.deleted,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
            production_time_budget=entity.production_time_budget,
            required_delivery_date_made=entity.required_delivery_date_made,
            required_delivery_date_bought=entity.required_delivery_date_bought,
            edit_version=entity.edit_version,
        )
