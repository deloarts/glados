"""
Reads one contact by id, or a filtered page of contacts. Both need
read:contacts, since contacts are personal data.
"""

from src.modules.catalogue.application.dto.contact_dto import ContactResult
from src.modules.catalogue.application.dto.contact_dto import PaginatedContacts
from src.modules.catalogue.application.mappers.contact_mapper import ContactMapper
from src.modules.catalogue.domain.errors import ContactNotFoundError
from src.modules.catalogue.domain.services.contact_rules import ContactRules
from src.modules.catalogue.ports.outbound.repositories.contact_repository import ContactFilterDto
from src.modules.catalogue.ports.outbound.repositories.contact_repository import IContactRepository
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User


class GetContact:
    def __init__(self, contact_repo: IContactRepository) -> None:
        self._contacts = contact_repo

    async def execute(self, actor: User, contact_id: int) -> ContactResult:
        ContactRules.assert_can_read(actor)
        contact = found_or_raise(
            await self._contacts.get_by_id(contact_id),
            ContactNotFoundError,
            f"Contact #{contact_id} not found.",
        )
        return ContactMapper.to_result(contact)


class GetContacts:
    def __init__(self, contact_repo: IContactRepository) -> None:
        self._contacts = contact_repo

    async def execute(self, actor: User, filters: ContactFilterDto) -> PaginatedContacts:
        ContactRules.assert_can_read(actor)
        total, contacts = await self._contacts.get_multi(filters)
        return PaginatedContacts(total=total, items=[ContactMapper.to_result(c) for c in contacts])
