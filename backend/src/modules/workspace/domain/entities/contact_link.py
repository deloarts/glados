"""
A contact linked to a product or a project, with whether the contact
receives the meeting notes. Workspace refers to the contact by id; the
contact itself is Catalogue's.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.workspace.domain.value_objects.contact_link_owner import ContactLinkOwner
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class ContactLink(Entity):
    owner: ContactLinkOwner
    # The product's or the project's id, as `owner` says.
    owner_id: int
    contact_id: int
    receives_meeting_notes: bool
    created: datetime
    creator_id: int
