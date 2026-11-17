"""
Updates a contact's details and organisation. An anonymised contact cannot
be edited, and the mail flags stay limited to a supplier's contact.
"""

from src.modules.catalogue.application.dto.contact_dto import ContactResult
from src.modules.catalogue.application.dto.contact_dto import UpdateContactCommand
from src.modules.catalogue.application.mappers.contact_mapper import ContactMapper
from src.modules.catalogue.application.use_cases.contact._values import assert_valid_organisation
from src.modules.catalogue.application.use_cases.contact._values import optional_text
from src.modules.catalogue.application.use_cases.contact._values import required_name
from src.modules.catalogue.domain.errors import ContactNotFoundError
from src.modules.catalogue.domain.services.contact_rules import ContactRules
from src.modules.catalogue.ports.outbound.repositories.contact_repository import IContactRepository
from src.modules.catalogue.ports.outbound.repositories.customer_repository import (
    ICustomerRepository,
)
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class UpdateContact:
    def __init__(
        self,
        contact_repo: IContactRepository,
        customer_repo: ICustomerRepository,
        supplier_repo: ISupplierRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._contacts = contact_repo
        self._customers = customer_repo
        self._suppliers = supplier_repo
        self._uow = uow

    async def execute(
        self, actor: User, contact_id: int, cmd: UpdateContactCommand
    ) -> ContactResult:
        ContactRules.assert_can_write(actor)

        await self._contacts.lock_for_update(contact_id)
        contact = found_or_raise(
            await self._contacts.get_by_id(contact_id),
            ContactNotFoundError,
            f"Contact #{contact_id} not found.",
        )
        assert_edit_version(contact, cmd.expected_edit_version, what=f"Contact #{contact.id}")
        ContactRules.assert_not_anonymised(contact)
        await assert_valid_organisation(
            self._customers,
            self._suppliers,
            customer_id=cmd.customer_id,
            supplier_id=cmd.supplier_id,
            receives_request_mails=cmd.receives_request_mails,
            receives_order_mails=cmd.receives_order_mails,
        )

        contact.name = required_name(cmd.name)
        contact.role = optional_text(cmd.role)
        contact.email = optional_text(cmd.email)
        contact.phone = optional_text(cmd.phone)
        contact.mobile = optional_text(cmd.mobile)
        contact.note = optional_text(cmd.note)
        contact.customer_id = cmd.customer_id
        contact.supplier_id = cmd.supplier_id
        contact.receives_request_mails = cmd.receives_request_mails
        contact.receives_order_mails = cmd.receives_order_mails
        contact.changed = now_utc()

        saved = await self._contacts.save(contact)
        await self._uow.commit()

        log.info(f"Updated contact ID={saved.id}.")

        return ContactMapper.to_result(saved)
