"""
Where contacts are used in Workspace: the live products and the projects
that link each of them and the meetings they attend or own todos in, for
the Used In column of the contacts tab. Needs read:contacts.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.workspace.application.dto.contact_link_dto import ContactUsageMeetingResult
from src.modules.workspace.application.dto.contact_link_dto import ContactUsageRecordResult
from src.modules.workspace.application.dto.contact_link_dto import ContactUsageResult
from src.modules.workspace.domain.services.contact_link_rules import ContactLinkRules
from src.modules.workspace.domain.value_objects.contact_link_owner import ContactLinkOwner
from src.modules.workspace.ports.outbound.repositories.contact_link_repository import (
    IContactLinkRepository,
)
from src.modules.workspace.ports.outbound.repositories.meeting_repository import IMeetingRepository


class GetContactUsage:
    def __init__(self, link_repo: IContactLinkRepository, meeting_repo: IMeetingRepository) -> None:
        self._links = link_repo
        self._meetings = meeting_repo

    async def execute(self, actor: User, contact_ids: list[int]) -> list[ContactUsageResult]:
        """One result per requested contact, in the order asked, also for a
        contact nothing links."""
        ContactLinkRules.assert_can_read(actor)
        ordered = list(dict.fromkeys(contact_ids))
        usage = {
            contact_id: ContactUsageResult(
                contact_id=contact_id, products=[], projects=[], meetings=[]
            )
            for contact_id in ordered
        }
        for row in await self._links.get_usage(ordered):
            entry = usage.get(row.contact_id)
            if entry is None:
                continue
            record = ContactUsageRecordResult(
                owner=row.owner,
                id=row.owner_id,
                number=row.number,
                receives_meeting_notes=row.receives_meeting_notes,
            )
            if row.owner == ContactLinkOwner.PRODUCT:
                entry.products.append(record)
            else:
                entry.projects.append(record)
        for meeting in await self._meetings.get_contact_usage(ordered):
            entry = usage.get(meeting.contact_id)
            if entry is not None:
                entry.meetings.append(
                    ContactUsageMeetingResult(
                        id=meeting.meeting_id,
                        meeting_number=meeting.meeting_number,
                        name=meeting.name,
                    )
                )
        return list(usage.values())
