"""
Converts between Product domain entity and DTOs.
"""

from src.modules.catalogue.application.mappers.customer_mapper import CustomerMapper
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.workspace.application.dto.product_dto import ProductResult
from src.modules.workspace.domain.entities.product import Product


class ProductMapper:
    @staticmethod
    def to_result(entity: Product) -> ProductResult:
        return ProductResult(
            id=entity.id,
            edit_version=entity.edit_version,
            public_id=entity.public_id,
            product_number=entity.product_number,
            customer_id=entity.customer_id,
            customer=CustomerMapper.to_result(entity.customer) if entity.customer else None,
            description=entity.description,
            designation=entity.designation,
            machine_type=entity.machine_type,
            installation_site=entity.installation_site,
            installation_location=entity.installation_location,
            planned_placing_on_market=entity.planned_placing_on_market,
            legal_basis=entity.legal_basis,
            plc_environment_id=entity.plc_environment_id,
            contains_pneumatics=entity.contains_pneumatics,
            contains_hydraulics=entity.contains_hydraulics,
            contains_electrics=entity.contains_electrics,
            contains_robotics=entity.contains_robotics,
            is_active=entity.is_active,
            designated_user_id=entity.designated_user_id,
            created=entity.created,
            archived=entity.archived,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
        )
