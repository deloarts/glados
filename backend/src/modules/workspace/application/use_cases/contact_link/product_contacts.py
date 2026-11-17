"""
The contacts of a product: list them, link one, set whether it receives the
meeting notes, and unlink it. Every project of the product inherits these
links. Reading needs read:contacts and every change write:contacts; each
change answers the product's list as it is afterwards.
"""

from src.modules.catalogue.ports.outbound.catalogue_queries import IContactQueries
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.application.dto.contact_link_dto import LinkContactCommand
from src.modules.workspace.application.dto.contact_link_dto import ProductContactResult
from src.modules.workspace.application.use_cases.contact_link._support import linkable_contact
from src.modules.workspace.application.use_cases.contact_link._support import load_product
from src.modules.workspace.application.use_cases.contact_link._support import product_contacts
from src.modules.workspace.domain.entities.contact_link import ContactLink
from src.modules.workspace.domain.errors import ContactAlreadyLinkedError
from src.modules.workspace.domain.errors import ContactLinkNotFoundError
from src.modules.workspace.domain.errors import ProductArchivedError
from src.modules.workspace.domain.services.contact_link_rules import ContactLinkRules
from src.modules.workspace.domain.services.product_rules import ProductRules
from src.modules.workspace.domain.value_objects.contact_link_owner import ContactLinkOwner
from src.modules.workspace.ports.outbound.repositories.contact_link_repository import (
    IContactLinkRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository
from src.shared_kernel.domain.services.clock import now_utc


class _ProductContactUseCase:
    def __init__(
        self,
        link_repo: IContactLinkRepository,
        product_repo: IProductRepository,
        contact_queries: IContactQueries,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._links = link_repo
        self._products = product_repo
        self._contacts = contact_queries
        self._uow = uow

    async def _existing(self, product_id: int, contact_id: int) -> ContactLink:
        link = await self._links.get_link(ContactLinkOwner.PRODUCT, product_id, contact_id)
        if link is None:
            raise ContactLinkNotFoundError(
                f"Contact #{contact_id} is not linked to product #{product_id}."
            )
        return link


class GetProductContacts(_ProductContactUseCase):
    async def execute(self, actor: User, product_id: int) -> list[ProductContactResult]:
        ContactLinkRules.assert_can_read(actor)
        await load_product(self._products, product_id)
        return await product_contacts(self._links, self._contacts, product_id)


class LinkProductContact(_ProductContactUseCase):
    async def execute(
        self, actor: User, product_id: int, cmd: LinkContactCommand
    ) -> list[ProductContactResult]:
        product = await load_product(self._products, product_id)
        ProductRules.assert_can_update(actor, product)
        if product.archived:
            raise ProductArchivedError(f"Product #{product_id} is archived.")
        await linkable_contact(self._contacts, cmd.contact_id)
        if await self._links.get_link(ContactLinkOwner.PRODUCT, product_id, cmd.contact_id):
            raise ContactAlreadyLinkedError(
                f"Contact #{cmd.contact_id} is linked to product #{product_id} already."
            )
        await self._links.save(
            ContactLink(
                id=0,
                owner=ContactLinkOwner.PRODUCT,
                owner_id=product_id,
                contact_id=cmd.contact_id,
                receives_meeting_notes=cmd.receives_meeting_notes,
                created=now_utc(),
                creator_id=actor.id,
            )
        )
        await self._uow.commit()
        log.info(f"Linked contact ID={cmd.contact_id} to product ID={product_id}.")
        return await product_contacts(self._links, self._contacts, product_id)


class SetProductContactMeetingNotes(_ProductContactUseCase):
    async def execute(
        self, actor: User, product_id: int, contact_id: int, receives_meeting_notes: bool
    ) -> list[ProductContactResult]:
        product = await load_product(self._products, product_id)
        ProductRules.assert_can_update(actor, product)
        link = await self._existing(product_id, contact_id)
        if link.receives_meeting_notes != receives_meeting_notes:
            link.receives_meeting_notes = receives_meeting_notes
            await self._links.save(link)
            await self._uow.commit()
        return await product_contacts(self._links, self._contacts, product_id)


class UnlinkProductContact(_ProductContactUseCase):
    async def execute(
        self, actor: User, product_id: int, contact_id: int
    ) -> list[ProductContactResult]:
        product = await load_product(self._products, product_id)
        ProductRules.assert_can_update(actor, product)
        link = await self._existing(product_id, contact_id)
        await self._links.delete(link)
        await self._uow.commit()
        log.info(f"Unlinked contact ID={contact_id} from product ID={product_id}.")
        return await product_contacts(self._links, self._contacts, product_id)
