"""
What the product and project contact link use cases share: loading the
owner and the contacts, and building the results in the order the sections
show them, by contact name.
"""

from src.modules.catalogue.application.dto.contact_dto import ContactSummaryResult
from src.modules.catalogue.application.mappers.contact_mapper import ContactMapper
from src.modules.catalogue.domain.entities.contact import Contact
from src.modules.catalogue.ports.outbound.catalogue_queries import IContactQueries
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.workspace.application.dto.contact_link_dto import ProductContactResult
from src.modules.workspace.application.dto.contact_link_dto import ProjectContactResult
from src.modules.workspace.domain.entities.contact_link import ContactLink
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.errors import ContactLinkInvalidError
from src.modules.workspace.domain.errors import ProductNotFoundError
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.services.contact_link_rules import ContactLinkRules
from src.modules.workspace.domain.value_objects.contact_link_owner import ContactLinkOwner
from src.modules.workspace.ports.outbound.repositories.contact_link_repository import (
    IContactLinkRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository
from src.modules.workspace.ports.outbound.repositories.project_repository import IProjectRepository


async def load_product(products: IProductRepository, product_id: int) -> Product:
    return found_or_raise(
        await products.get_by_id(product_id),
        ProductNotFoundError,
        f"Product #{product_id} not found.",
    )


async def load_project(projects: IProjectRepository, project_id: int) -> Project:
    project = await projects.get_by_id(project_id)
    if project is None or project.deleted:
        raise ProjectNotFoundError(f"Project #{project_id} not found.")
    return project


async def linkable_contact(contacts: IContactQueries, contact_id: int) -> Contact:
    """A contact a new link may name: one that exists and is not archived."""
    contact = await contacts.get_by_id(contact_id)
    if contact is None:
        raise ContactLinkInvalidError(f"Contact #{contact_id} not found.")
    if contact.archived:
        raise ContactLinkInvalidError(f"Contact #{contact_id} is archived.")
    return contact


async def _summaries(
    contacts: IContactQueries, contact_ids: list[int]
) -> dict[int, ContactSummaryResult]:
    found = await contacts.get_by_ids(contact_ids)
    return {contact.id: ContactMapper.to_summary(contact) for contact in found}


def _by_name(summary: ContactSummaryResult) -> tuple[bool, str, int]:
    return (summary.anonymised, summary.name.casefold(), summary.id)


async def product_contacts(
    links: IContactLinkRepository, contacts: IContactQueries, product_id: int
) -> list[ProductContactResult]:
    rows = await links.get_links(ContactLinkOwner.PRODUCT, product_id)
    summaries = await _summaries(contacts, [row.contact_id for row in rows])
    results = [
        ProductContactResult(
            contact=summaries[row.contact_id], receives_meeting_notes=row.receives_meeting_notes
        )
        for row in rows
        if row.contact_id in summaries
    ]
    return sorted(results, key=lambda result: _by_name(result.contact))


async def product_links_of(links: IContactLinkRepository, project: Project) -> list[ContactLink]:
    if project.product_id is None:
        return []
    return await links.get_links(ContactLinkOwner.PRODUCT, project.product_id)


async def project_contacts(
    links: IContactLinkRepository, contacts: IContactQueries, project: Project
) -> list[ProjectContactResult]:
    resolved = ContactLinkRules.resolve_project_contacts(
        await product_links_of(links, project),
        await links.get_links(ContactLinkOwner.PROJECT, project.id),
    )
    summaries = await _summaries(contacts, [entry.contact_id for entry in resolved])
    results = [
        ProjectContactResult(
            contact=summaries[entry.contact_id],
            inherited=entry.inherited,
            receives_meeting_notes=entry.receives_meeting_notes,
            product_receives_meeting_notes=entry.product_receives_meeting_notes,
            overridden=entry.overridden,
        )
        for entry in resolved
        if entry.contact_id in summaries
    ]
    # The inherited contacts first, as the product shows them, then the
    # project's own.
    return sorted(results, key=lambda result: (not result.inherited, *_by_name(result.contact)))
