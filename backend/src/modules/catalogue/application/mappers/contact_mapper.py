"""
Converts the Contact domain entity into its result DTOs.
"""

from src.modules.catalogue.application.dto.contact_dto import ContactOrganisationResult
from src.modules.catalogue.application.dto.contact_dto import ContactResult
from src.modules.catalogue.application.dto.contact_dto import ContactSummaryResult
from src.modules.catalogue.domain.entities.contact import Contact
from src.modules.platform.application.mappers.user_mapper import UserMapper


class ContactMapper:
    @staticmethod
    def organisation(entity: Contact) -> ContactOrganisationResult | None:
        kind = entity.organisation_kind
        organisation_id = (
            entity.customer_id if entity.customer_id is not None else entity.supplier_id
        )
        if kind is None or organisation_id is None:
            return None
        return ContactOrganisationResult(
            kind=kind,
            id=organisation_id,
            name=entity.organisation_name or "",
            archived=entity.organisation_archived,
        )

    @staticmethod
    def to_summary(entity: Contact) -> ContactSummaryResult:
        return ContactSummaryResult(
            id=entity.id,
            public_id=entity.public_id,
            name=entity.name,
            role=entity.role,
            email=entity.email,
            phone=entity.phone,
            mobile=entity.mobile,
            archived=entity.archived,
            anonymised=entity.anonymised,
            organisation=ContactMapper.organisation(entity),
        )

    @staticmethod
    def to_result(entity: Contact) -> ContactResult:
        return ContactResult(
            id=entity.id,
            public_id=entity.public_id,
            edit_version=entity.edit_version,
            created=entity.created,
            changed=entity.changed,
            archived=entity.archived,
            anonymised_at=entity.anonymised_at,
            name=entity.name,
            role=entity.role,
            email=entity.email,
            phone=entity.phone,
            mobile=entity.mobile,
            note=entity.note,
            customer_id=entity.customer_id,
            supplier_id=entity.supplier_id,
            organisation=ContactMapper.organisation(entity),
            receives_request_mails=entity.receives_request_mails,
            receives_order_mails=entity.receives_order_mails,
            creator_id=entity.creator_id,
            creator=UserMapper.to_public_result(entity.creator) if entity.creator else None,
            changed_by_id=entity.changed_by_id,
            changed_by=UserMapper.to_public_result(entity.changed_by)
            if entity.changed_by
            else None,
        )
