"""
Blanks the copies of an anonymised contact or guest in a snapshot of
meeting notes: the name and e-mail address of its attendee rows, the name
of the todos it owns and its address among the recipients, which reads as
an empty address afterwards. The checksum and everything else stay, as
proof of what went out. No I/O.
"""

from src.modules.workspace.domain.entities.meeting_snapshot import MeetingSnapshot
from src.modules.workspace.domain.entities.meeting_snapshot import SnapshotAttendee


def _blank_attendee(attendee: SnapshotAttendee) -> None:
    attendee.name, attendee.email, attendee.anonymised = "", None, True


def _scrub(addresses: list[str], blanked: set[str]) -> list[str]:
    return ["" if address.casefold() in blanked else address for address in addresses]


def _scrub_recipients(snapshot: MeetingSnapshot, blanked: set[str]) -> None:
    snapshot.recipients = _scrub(snapshot.recipients, blanked)
    snapshot.cc = _scrub(snapshot.cc, blanked)


def contact_addresses(snapshot: MeetingSnapshot, contact_id: int) -> set[str]:
    """The addresses the snapshot's attendee rows kept for the contact."""
    return {
        a.email.casefold() for a in snapshot.attendees if a.contact_id == contact_id and a.email
    }


def blank_contact(snapshot: MeetingSnapshot, contact_id: int, addresses: set[str]) -> None:
    """Blanks the contact's copies, and every address of `addresses`, kept
    in lower case, among the recipients."""
    for attendee in snapshot.attendees:
        if attendee.contact_id == contact_id:
            _blank_attendee(attendee)
    for card in snapshot.cards:
        for todo in card.todos:
            for owner in todo.owners:
                if owner.contact_id == contact_id:
                    owner.name = ""
    _scrub_recipients(snapshot, addresses)


def guest_addresses(snapshot: MeetingSnapshot, attendee_id: int) -> set[str]:
    return {a.email.casefold() for a in snapshot.attendees if a.id == attendee_id and a.email}


def blank_guest(snapshot: MeetingSnapshot, attendee_id: int, addresses: set[str]) -> None:
    """Blanks the guest's attendee row and its addresses among the
    recipients."""
    for attendee in snapshot.attendees:
        if attendee.id == attendee_id:
            _blank_attendee(attendee)
    _scrub_recipients(snapshot, addresses)
