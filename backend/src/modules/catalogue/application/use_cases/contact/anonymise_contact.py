"""
Anonymises a contact: blanks its name, e-mail address, phone and mobile
numbers and note, takes away its mail flags and archives it. The row stays,
so everything that links it keeps resolving, and it can neither be edited
nor restored afterwards. Running it again changes nothing.

The copies of the name and address that other records keep, such as the
attendees and todo owners of meetings, are blanked in the same commit through
the contact copies port, which the modules keeping them implement. It needs
write:contacts together with manage:meetings, since it reaches the meetings.
"""

from src.modules.catalogue.application.dto.contact_dto import ContactResult
from src.modules.catalogue.application.mappers.contact_mapper import ContactMapper
from src.modules.catalogue.domain.errors import ContactNotFoundError
from src.modules.catalogue.domain.services.contact_rules import ContactRules
from src.modules.catalogue.ports.outbound.contact_copies_port import IContactCopies
from src.modules.catalogue.ports.outbound.repositories.contact_repository import IContactRepository
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class AnonymiseContact:
    def __init__(
        self,
        contact_repo: IContactRepository,
        copies: IContactCopies | None = None,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._contacts = contact_repo
        self._copies = copies
        self._uow = uow

    async def execute(self, actor: User, contact_id: int) -> ContactResult:
        ContactRules.assert_can_anonymise(actor)

        await self._contacts.lock_for_update(contact_id)
        contact = found_or_raise(
            await self._contacts.get_by_id(contact_id),
            ContactNotFoundError,
            f"Contact #{contact_id} not found.",
        )
        if contact.anonymised:
            return ContactMapper.to_result(contact)

        now = now_utc()
        previous_email = contact.email
        contact.name = ""
        contact.email = None
        contact.phone = None
        contact.mobile = None
        contact.note = None
        contact.receives_request_mails = False
        contact.receives_order_mails = False
        contact.archived = True
        contact.anonymised_at = now
        contact.changed = now

        saved = await self._contacts.save(contact)
        if self._copies is not None:
            await self._copies.anonymise_copies(saved.id, previous_email)
        await self._uow.commit()

        log.info(f"Anonymised contact ID={saved.id}.")

        return ContactMapper.to_result(saved)
