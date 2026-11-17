"""
Row mapping of contacts, used by the repository and by other modules'
persistence adapters that load a related row.
"""

from src.modules.catalogue.adapters.outbound.persistence.models.contact_model import ContactOrmModel
from src.modules.catalogue.domain.entities.contact import Contact
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware


def contact_orm_to_entity(orm: ContactOrmModel) -> Contact:
    """Reads the organisation's name and archived flag, so the row must be
    loaded with its customer and supplier (contact_load_options)."""
    organisation = orm.customer if orm.customer_id is not None else orm.supplier
    return Contact(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        changed=utc_aware(orm.changed),
        archived=orm.archived,
        anonymised_at=utc_aware(orm.anonymised_at),
        name=orm.name,
        role=orm.role,
        email=orm.email,
        phone=orm.phone,
        mobile=orm.mobile,
        note=orm.note,
        customer_id=orm.customer_id,
        supplier_id=orm.supplier_id,
        receives_request_mails=orm.receives_request_mails,
        receives_order_mails=orm.receives_order_mails,
        organisation_name=organisation.name if organisation is not None else None,
        organisation_archived=organisation.archived if organisation is not None else False,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        edit_version=orm.edit_version,
    )
