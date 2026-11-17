"""
The contacts a supplier's request and order mails go to: its live contacts
with an e-mail address and the matching flag. The mail dialogs fill To from
them and fall back to the supplier's own address when none is flagged.
"""

from src.modules.catalogue.application.dto.contact_dto import SupplierMailRecipientResult
from src.modules.catalogue.application.dto.contact_dto import SupplierMailRecipientsResult
from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.catalogue.domain.services.contact_rules import ContactRules
from src.modules.catalogue.ports.outbound.repositories.contact_repository import IContactRepository
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User


class GetSupplierMailRecipients:
    def __init__(
        self, contact_repo: IContactRepository, supplier_repo: ISupplierRepository
    ) -> None:
        self._contacts = contact_repo
        self._suppliers = supplier_repo

    async def execute(self, actor: User, supplier_id: int) -> SupplierMailRecipientsResult:
        ContactRules.assert_can_read_mail_recipients(actor)
        found_or_raise(
            await self._suppliers.get_by_id(supplier_id),
            SupplierNotFoundError,
            f"Supplier #{supplier_id} not found.",
        )
        contacts = await self._contacts.get_mail_recipients(supplier_id)
        request: list[SupplierMailRecipientResult] = []
        order: list[SupplierMailRecipientResult] = []
        for contact in contacts:
            if not contact.email:
                continue
            recipient = SupplierMailRecipientResult(
                contact_id=contact.id, name=contact.name, email=contact.email
            )
            if contact.receives_request_mails:
                request.append(recipient)
            if contact.receives_order_mails:
                order.append(recipient)
        return SupplierMailRecipientsResult(supplier_id=supplier_id, request=request, order=order)
