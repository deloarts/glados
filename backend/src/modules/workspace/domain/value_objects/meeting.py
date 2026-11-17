"""
The closed vocabularies of meetings: what owns a meeting, the kinds and
statuses of attendees, the icons a card's scope can carry, the kinds of
history events and the categories of meeting files.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class MeetingOwnerKind(StrValueEnum):
    PROJECT = "project"
    PRODUCT = "product"


@unique
class MeetingAttendeeKind(StrValueEnum):
    """A Glados user, a contact, or a guest known only by a name and an
    optional e-mail address."""

    USER = "user"
    CONTACT = "contact"
    GUEST = "guest"


@unique
class MeetingAttendanceStatus(StrValueEnum):
    """Present and excused attend or miss the meeting; distribution only
    receives the minutes without attending."""

    PRESENT = "present"
    EXCUSED = "excused"
    DISTRIBUTION_ONLY = "distribution_only"


@unique
class MeetingScopeIcon(StrValueEnum):
    """The fixed set of icons a card's scope can show. The frontend maps
    each identifier to its glyph."""

    TOPIC = "topic"
    SCHEDULE = "schedule"
    DECISION = "decision"
    MECHANICS = "mechanics"
    ELECTRICAL = "electrical"
    SOFTWARE = "software"
    COMMERCIAL = "commercial"
    LOGISTICS = "logistics"
    QUALITY = "quality"
    SAFETY = "safety"
    SITE = "site"
    RISK = "risk"


@unique
class MeetingEventKind(StrValueEnum):
    """What the history of a meeting records. Printing, downloading and
    sending are written by the distribution of the notes, the others by the
    meeting's own use cases."""

    CREATED = "created"
    EDITED = "edited"
    CARD_ADDED = "card_added"
    CARD_CHANGED = "card_changed"
    CARD_DELETED = "card_deleted"
    # Cards, decisions and todos added at once from a reviewed draft.
    IMPORTED = "imported"
    TODO_ADDED = "todo_added"
    TODO_DONE = "todo_done"
    TODO_REOPENED = "todo_reopened"
    FILE_ADDED = "file_added"
    FILE_DELETED = "file_deleted"
    PRINTED = "printed"
    DOWNLOADED = "downloaded"
    SENT = "sent"
    MARKED_INVALID = "marked_invalid"
    RESTORED = "restored"


@unique
class MeetingFileCategory(StrValueEnum):
    """Images, such as those pasted into a card, and PDF documents. A
    meeting holds any number of each."""

    IMAGE = "image"
    PDF = "pdf"

    @classmethod
    def images(cls) -> frozenset["MeetingFileCategory"]:
        return frozenset({cls.IMAGE})

    def is_singleton(self) -> bool:
        return False


@unique
class MeetingDistributionKind(StrValueEnum):
    """How the notes of a meeting left Glados: printed on a printer,
    downloaded as a PDF or sent by mail with the PDF attached."""

    PRINTED = "printed"
    DOWNLOADED = "downloaded"
    SENT = "sent"
