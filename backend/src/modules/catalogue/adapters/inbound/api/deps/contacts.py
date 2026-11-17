"""Use case factories: contacts."""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.bindings import get_contact_copies
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_contact_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_customer_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_supplier_repo
from src.modules.catalogue.application.use_cases.contact.anonymise_contact import AnonymiseContact
from src.modules.catalogue.application.use_cases.contact.archive_contact import ArchiveContact
from src.modules.catalogue.application.use_cases.contact.archive_contact import RestoreContact
from src.modules.catalogue.application.use_cases.contact.create_contact import CreateContact
from src.modules.catalogue.application.use_cases.contact.get_contact import GetContact
from src.modules.catalogue.application.use_cases.contact.get_contact import GetContacts
from src.modules.catalogue.application.use_cases.contact.get_supplier_mail_recipients import (
    GetSupplierMailRecipients,
)
from src.modules.catalogue.application.use_cases.contact.update_contact import UpdateContact
from src.modules.catalogue.ports.outbound.contact_copies_port import IContactCopies
from src.modules.catalogue.ports.outbound.repositories.contact_repository import IContactRepository
from src.modules.catalogue.ports.outbound.repositories.customer_repository import (
    ICustomerRepository,
)
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_contact_use_case(
    contact_repo: IContactRepository = Depends(get_contact_repo),
) -> GetContact:
    return GetContact(contact_repo=contact_repo)


def get_contacts_use_case(
    contact_repo: IContactRepository = Depends(get_contact_repo),
) -> GetContacts:
    return GetContacts(contact_repo=contact_repo)


def get_create_contact_use_case(
    contact_repo: IContactRepository = Depends(get_contact_repo),
    customer_repo: ICustomerRepository = Depends(get_customer_repo),
    supplier_repo: ISupplierRepository = Depends(get_supplier_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateContact:
    return CreateContact(
        contact_repo=contact_repo, customer_repo=customer_repo, supplier_repo=supplier_repo, uow=uow
    )


def get_update_contact_use_case(
    contact_repo: IContactRepository = Depends(get_contact_repo),
    customer_repo: ICustomerRepository = Depends(get_customer_repo),
    supplier_repo: ISupplierRepository = Depends(get_supplier_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateContact:
    return UpdateContact(
        contact_repo=contact_repo, customer_repo=customer_repo, supplier_repo=supplier_repo, uow=uow
    )


def get_archive_contact_use_case(
    contact_repo: IContactRepository = Depends(get_contact_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ArchiveContact:
    return ArchiveContact(contact_repo=contact_repo, uow=uow)


def get_restore_contact_use_case(
    contact_repo: IContactRepository = Depends(get_contact_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RestoreContact:
    return RestoreContact(contact_repo=contact_repo, uow=uow)


def get_anonymise_contact_use_case(
    contact_repo: IContactRepository = Depends(get_contact_repo),
    copies: IContactCopies = Depends(get_contact_copies),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> AnonymiseContact:
    return AnonymiseContact(contact_repo=contact_repo, copies=copies, uow=uow)


def get_supplier_mail_recipients_use_case(
    contact_repo: IContactRepository = Depends(get_contact_repo),
    supplier_repo: ISupplierRepository = Depends(get_supplier_repo),
) -> GetSupplierMailRecipients:
    return GetSupplierMailRecipients(contact_repo=contact_repo, supplier_repo=supplier_repo)
