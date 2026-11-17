"""
Row mapping of customers, used by the repository and by other modules'
persistence adapters that load a related row.
"""

from src.modules.catalogue.adapters.outbound.persistence.models.customer_model import (
    CustomerOrmModel,
)
from src.modules.catalogue.domain.entities.customer import Customer
from src.modules.catalogue.domain.value_objects.customer_level import CustomerLevel
from src.modules.platform.adapters.outbound.persistence.mapping_common import archived_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware


def customer_orm_to_entity(orm: CustomerOrmModel) -> Customer:
    return Customer(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        name=orm.name,
        legal_name=orm.legal_name,
        vat_id=orm.vat_id,
        level=CustomerLevel(orm.level),
        street=orm.street,
        city=orm.city,
        country=orm.country,
        postal_code=orm.postal_code,
        email=orm.email,
        phone=orm.phone,
        weblink=orm.weblink,
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        edit_version=orm.edit_version,
    )
