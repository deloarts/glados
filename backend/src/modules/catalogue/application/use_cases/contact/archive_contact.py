"""
Archives or restores a contact. An archived contact stays on the products,
projects and records that link it, but is no longer offered for new links.
Both are idempotent, and an anonymised contact cannot be restored.
"""

from src.modules.catalogue.application.dto.contact_dto import ContactResult
from src.modules.catalogue.application.mappers.contact_mapper import ContactMapper
from src.modules.catalogue.domain.entities.contact import Contact
from src.modules.catalogue.domain.errors import ContactNotFoundError
from src.modules.catalogue.domain.services.contact_rules import ContactRules
from src.modules.catalogue.ports.outbound.repositories.contact_repository import IContactRepository
from src.modules.platform.application.services.archive_restore import set_archived
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class ArchiveContact:
    def __init__(self, contact_repo: IContactRepository, *, uow: IUnitOfWork) -> None:
        self._contacts = contact_repo
        self._uow = uow

    async def execute(self, actor: User, contact_id: int) -> ContactResult:
        ContactRules.assert_can_write(actor)

        async def _stamp(contact: Contact) -> None:
            if not contact.archived:
                contact.changed = now_utc()

        saved = await set_archived(
            entity_id=contact_id,
            archived=True,
            load=self._contacts.get_by_id,
            not_found=lambda cid: ContactNotFoundError(f"Contact #{cid} not found."),
            save=self._contacts.save,
            before_save=_stamp,
        )
        await self._uow.commit()

        log.info(f"Archived contact ID={saved.id}.")

        return ContactMapper.to_result(saved)


class RestoreContact:
    def __init__(self, contact_repo: IContactRepository, *, uow: IUnitOfWork) -> None:
        self._contacts = contact_repo
        self._uow = uow

    async def execute(self, actor: User, contact_id: int) -> ContactResult:
        ContactRules.assert_can_write(actor)

        async def _guard(contact: Contact) -> None:
            ContactRules.assert_not_anonymised(contact)
            if contact.archived:
                contact.changed = now_utc()

        saved = await set_archived(
            entity_id=contact_id,
            archived=False,
            load=self._contacts.get_by_id,
            not_found=lambda cid: ContactNotFoundError(f"Contact #{cid} not found."),
            save=self._contacts.save,
            before_save=_guard,
        )
        await self._uow.commit()

        log.info(f"Restored contact ID={saved.id}.")

        return ContactMapper.to_result(saved)
