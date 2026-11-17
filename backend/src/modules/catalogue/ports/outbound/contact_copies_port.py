"""
The copies of a contact's name and address that other modules keep, such as
the attendees and todo owners of meetings in Workspace. Anonymising a contact
blanks them through this port, which Catalogue owns and Workspace implements.
"""

from typing import Protocol


class IContactCopies(Protocol):
    async def anonymise_copies(self, contact_id: int, email: str | None = None) -> None:
        """Blanks every copy of the contact's name and e-mail address that the
        implementing module keeps, without committing. `email` is the address
        the contact had before it was anonymised, so a copy kept only as an
        address, such as the recipient of a sent mail, is found too."""
        ...
