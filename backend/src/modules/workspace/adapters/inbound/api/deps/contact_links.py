"""Use case factories: the contact links of products and projects, and the
usage of contacts. The contacts themselves come through Catalogue's
contact repository, typed with the query port the use cases declare."""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_contact_repo
from src.modules.catalogue.ports.outbound.catalogue_queries import IContactQueries
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_contact_link_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_meeting_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_project_repo
from src.modules.workspace.application.use_cases.contact_link.contact_usage import GetContactUsage
from src.modules.workspace.application.use_cases.contact_link.product_contacts import (
    GetProductContacts,
)
from src.modules.workspace.application.use_cases.contact_link.product_contacts import (
    LinkProductContact,
)
from src.modules.workspace.application.use_cases.contact_link.product_contacts import (
    SetProductContactMeetingNotes,
)
from src.modules.workspace.application.use_cases.contact_link.product_contacts import (
    UnlinkProductContact,
)
from src.modules.workspace.application.use_cases.contact_link.project_contacts import (
    GetProjectContacts,
)
from src.modules.workspace.application.use_cases.contact_link.project_contacts import (
    LinkProjectContact,
)
from src.modules.workspace.application.use_cases.contact_link.project_contacts import (
    SetProjectContactMeetingNotes,
)
from src.modules.workspace.application.use_cases.contact_link.project_contacts import (
    UnlinkProjectContact,
)
from src.modules.workspace.ports.outbound.repositories.contact_link_repository import (
    IContactLinkRepository,
)
from src.modules.workspace.ports.outbound.repositories.meeting_repository import IMeetingRepository
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository
from src.modules.workspace.ports.outbound.repositories.project_repository import IProjectRepository


def _product_args(
    link_repo: IContactLinkRepository = Depends(get_contact_link_repo),
    product_repo: IProductRepository = Depends(get_product_repo),
    contact_queries: IContactQueries = Depends(get_contact_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> tuple[IContactLinkRepository, IProductRepository, IContactQueries, IUnitOfWork]:
    return link_repo, product_repo, contact_queries, uow


def _project_args(
    link_repo: IContactLinkRepository = Depends(get_contact_link_repo),
    project_repo: IProjectRepository = Depends(get_project_repo),
    contact_queries: IContactQueries = Depends(get_contact_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> tuple[IContactLinkRepository, IProjectRepository, IContactQueries, IUnitOfWork]:
    return link_repo, project_repo, contact_queries, uow


_ProductArgs = tuple[IContactLinkRepository, IProductRepository, IContactQueries, IUnitOfWork]
_ProjectArgs = tuple[IContactLinkRepository, IProjectRepository, IContactQueries, IUnitOfWork]


def get_product_contacts_use_case(
    args: _ProductArgs = Depends(_product_args),
) -> GetProductContacts:
    links, products, contacts, uow = args
    return GetProductContacts(links, products, contacts, uow=uow)


def get_link_product_contact_use_case(
    args: _ProductArgs = Depends(_product_args),
) -> LinkProductContact:
    links, products, contacts, uow = args
    return LinkProductContact(links, products, contacts, uow=uow)


def get_set_product_contact_meeting_notes_use_case(
    args: _ProductArgs = Depends(_product_args),
) -> SetProductContactMeetingNotes:
    links, products, contacts, uow = args
    return SetProductContactMeetingNotes(links, products, contacts, uow=uow)


def get_unlink_product_contact_use_case(
    args: _ProductArgs = Depends(_product_args),
) -> UnlinkProductContact:
    links, products, contacts, uow = args
    return UnlinkProductContact(links, products, contacts, uow=uow)


def get_project_contacts_use_case(
    args: _ProjectArgs = Depends(_project_args),
) -> GetProjectContacts:
    links, projects, contacts, uow = args
    return GetProjectContacts(links, projects, contacts, uow=uow)


def get_link_project_contact_use_case(
    args: _ProjectArgs = Depends(_project_args),
) -> LinkProjectContact:
    links, projects, contacts, uow = args
    return LinkProjectContact(links, projects, contacts, uow=uow)


def get_set_project_contact_meeting_notes_use_case(
    args: _ProjectArgs = Depends(_project_args),
) -> SetProjectContactMeetingNotes:
    links, projects, contacts, uow = args
    return SetProjectContactMeetingNotes(links, projects, contacts, uow=uow)


def get_unlink_project_contact_use_case(
    args: _ProjectArgs = Depends(_project_args),
) -> UnlinkProjectContact:
    links, projects, contacts, uow = args
    return UnlinkProjectContact(links, projects, contacts, uow=uow)


def get_contact_usage_use_case(
    link_repo: IContactLinkRepository = Depends(get_contact_link_repo),
    meeting_repo: IMeetingRepository = Depends(get_meeting_repo),
) -> GetContactUsage:
    return GetContactUsage(link_repo, meeting_repo)
