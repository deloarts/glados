"""
Pure business rules for contacts. No I/O.
"""

from src.modules.catalogue.domain.entities.contact import Contact
from src.modules.catalogue.domain.errors import ContactAnonymisedError
from src.modules.catalogue.domain.errors import ContactMailFlagsInvalidError
from src.modules.catalogue.domain.errors import ContactOrganisationInvalidError
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission


class ContactRules:
    # ── Permissions ───────────────────────────────────────────────────

    @staticmethod
    def assert_can_read(actor: User) -> None:
        assert_has_permission(actor, Permission.READ_CONTACTS, "read", "contacts")

    @staticmethod
    def assert_can_write(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_CONTACTS, "edit", "contacts")

    @staticmethod
    def assert_can_anonymise(actor: User) -> None:
        """Anonymising also blanks the contact on the meetings that name it,
        so it needs the right to manage meetings as well."""
        assert_has_permission(actor, Permission.WRITE_CONTACTS, "anonymise", "contacts")
        assert_has_permission(actor, Permission.MANAGE_MEETINGS, "anonymise", "contacts")

    @staticmethod
    def assert_can_read_mail_recipients(actor: User) -> None:
        """The flagged recipients of a supplier's mails are what a supplier
        mail is sent to, so whoever may send mail reads them, as they read
        the supplier's own recipient addresses."""
        if not (
            actor.has_permission(Permission.READ_CONTACTS)
            or actor.has_permission(Permission.SEND_MAIL)
        ):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.full_name}) cannot read the mail recipients of suppliers."
            )

    # ── Values ────────────────────────────────────────────────────────

    @staticmethod
    def assert_valid_organisation(customer_id: int | None, supplier_id: int | None) -> None:
        if customer_id is not None and supplier_id is not None:
            raise ContactOrganisationInvalidError(
                "A contact belongs to a customer or a supplier, not to both."
            )

    @staticmethod
    def assert_valid_mail_flags(
        supplier_id: int | None, receives_request_mails: bool, receives_order_mails: bool
    ) -> None:
        if supplier_id is None and (receives_request_mails or receives_order_mails):
            raise ContactMailFlagsInvalidError(
                "Only a supplier's contact receives the supplier's request and order mails."
            )

    @staticmethod
    def assert_not_anonymised(contact: Contact) -> None:
        if contact.anonymised:
            raise ContactAnonymisedError(f"Contact #{contact.id} was anonymised.")
