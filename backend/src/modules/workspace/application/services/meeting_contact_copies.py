"""
Workspace's side of Catalogue's contact copies port: anonymising a contact
blanks the copies of its name and e-mail address on the attendees and todo
owners of meetings, and in the snapshots of printed, downloaded and sent
notes, where its address among the recipients of a send is blanked in the
export journal as well. The checksums of the snapshots stay.
"""

from src.modules.workspace.domain.services.meeting_snapshot_anonymisation import blank_contact
from src.modules.workspace.domain.services.meeting_snapshot_anonymisation import contact_addresses
from src.modules.workspace.ports.outbound.meeting_notes_journal_port import IMeetingNotesJournal
from src.modules.workspace.ports.outbound.repositories.meeting_repository import IMeetingRepository
from src.modules.workspace.ports.outbound.repositories.meeting_repository import (
    IMeetingSnapshotRepository,
)
from src.shared_kernel.domain.services.clock import now_utc


class MeetingContactCopies:
    """Implements Catalogue's IContactCopies."""

    def __init__(
        self,
        meetings: IMeetingRepository,
        snapshots: IMeetingSnapshotRepository | None = None,
        journal: IMeetingNotesJournal | None = None,
    ) -> None:
        self._meetings = meetings
        self._snapshots = snapshots
        self._journal = journal

    async def anonymise_copies(self, contact_id: int, email: str | None = None) -> None:
        await self._meetings.anonymise_contact_copies(contact_id, now_utc())
        if self._snapshots is None:
            return
        entry_ids: list[int] = []
        blanked: set[str] = {email.casefold()} if email else set()
        snapshots = await self._snapshots.get_with_contact(contact_id)
        for snapshot in snapshots:
            blanked |= contact_addresses(snapshot, contact_id)
        for snapshot in snapshots:
            blank_contact(snapshot, contact_id, blanked)
            await self._snapshots.save_copies(snapshot)
            entry_ids.append(snapshot.journal_entry_id)
        if self._journal is not None and entry_ids and blanked:
            await self._journal.anonymise_recipients(entry_ids, blanked)
