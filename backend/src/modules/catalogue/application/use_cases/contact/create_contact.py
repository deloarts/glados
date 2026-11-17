"""
Creates a contact, of a customer, of a supplier or of neither. The mail
flags are only allowed on a supplier's contact. The log names the contact by
id only, since its name is personal data.
"""

from src.modules.catalogue.application.dto.contact_dto import ContactResult
from src.modules.catalogue.application.dto.contact_dto import CreateContactCommand
from src.modules.catalogue.application.mappers.contact_mapper import ContactMapper
from src.modules.catalogue.application.use_cases.contact._values import assert_valid_organisation
from src.modules.catalogue.application.use_cases.contact._values import optional_text
from src.modules.catalogue.application.use_cases.contact._values import required_name
from src.modules.catalogue.domain.entities.contact import Contact
from src.modules.catalogue.domain.services.contact_rules import ContactRules
from src.modules.catalogue.ports.outbound.repositories.contact_repository import IContactRepository
from src.modules.catalogue.ports.outbound.repositories.customer_repository import (
    ICustomerRepository,
)
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class CreateContact:
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

    async def execute(self, actor: User, cmd: CreateContactCommand) -> ContactResult:
        ContactRules.assert_can_write(actor)
        await assert_valid_organisation(
            self._customers,
            self._suppliers,
            customer_id=cmd.customer_id,
            supplier_id=cmd.supplier_id,
            receives_request_mails=cmd.receives_request_mails,
            receives_order_mails=cmd.receives_order_mails,
        )

        contact = Contact(
            id=0,
            created=now_utc(),
            changed=None,
            archived=False,
            anonymised_at=None,
            name=required_name(cmd.name),
            role=optional_text(cmd.role),
            email=optional_text(cmd.email),
            phone=optional_text(cmd.phone),
            mobile=optional_text(cmd.mobile),
            note=optional_text(cmd.note),
            customer_id=cmd.customer_id,
            supplier_id=cmd.supplier_id,
            receives_request_mails=cmd.receives_request_mails,
            receives_order_mails=cmd.receives_order_mails,
            creator_id=actor.id,
        )
        saved = await self._contacts.save(contact)
        await self._uow.commit()

        log.info(f"Created contact ID={saved.id}.")

        return ContactMapper.to_result(saved)
