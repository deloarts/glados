"""
Converts between Customer domain entity and DTOs.
"""

from src.modules.catalogue.application.dto.customer_dto import CustomerResult
from src.modules.catalogue.domain.entities.customer import Customer
from src.modules.platform.application.mappers.user_mapper import UserMapper


class CustomerMapper:
    @staticmethod
    def to_result(entity: Customer) -> CustomerResult:
        return CustomerResult(
            id=entity.id,
            edit_version=entity.edit_version,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            archived=entity.archived,
            name=entity.name,
            legal_name=entity.legal_name,
            vat_id=entity.vat_id,
            level=entity.level.value,
            street=entity.street,
            city=entity.city,
            country=entity.country,
            postal_code=entity.postal_code,
            email=entity.email,
            phone=entity.phone,
            weblink=entity.weblink,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
        )
