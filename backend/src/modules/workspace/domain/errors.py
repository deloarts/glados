"""The domain errors of Workspace.

Each error inherits a semantic base from Platform's domain/exceptions.py,
which the exception handler maps to an HTTP status. The response carries
the class name as its `code`, which clients and translations match on, so
an error keeps its name once it has shipped."""

from src.modules.platform.domain.exceptions import ConflictError
from src.modules.platform.domain.exceptions import InvalidInputError
from src.modules.platform.domain.exceptions import NotFoundError
from src.modules.platform.domain.exceptions import PayloadTooLargeError
from src.modules.platform.domain.exceptions import UnsupportedFileTypeError

# ── Products and product families ─────────────────────────────────────


class ProductNotFoundError(NotFoundError):
    pass


class ProductAlreadyExistsError(ConflictError):
    pass


class ProductNumberPatternError(InvalidInputError):
    pass


class ProductArchivedError(ConflictError):
    """Something new was attached to an archived product."""


# ── Product devices and variants ──────────────────────────────────────


class ProductDeviceOptionNotFoundError(NotFoundError):
    pass


class ProductDeviceOptionInvalidError(InvalidInputError):
    """A device list entry breaks a rule of its category: a driving medium
    without a letter, a letter on another category, or a letter that is
    not plain uppercase ASCII."""


class ProductDeviceLetterTakenError(ConflictError):
    """Another driving medium already uses this letter."""


class ProductDeviceLetterFrozenError(ConflictError):
    """The letter of a driving medium that devices already use cannot
    change, since it is part of their names."""


class ProductDeviceKindNotFoundError(NotFoundError):
    pass


class PlcEnvironmentNotFoundError(NotFoundError):
    pass


class PlcEnvironmentInvalidError(InvalidInputError):
    """A PLC environment breaks a rule: an empty or overlong name, an
    unknown prefix key, a tag length out of range, a conversion without a
    source or with a source twice, or an export column without a header."""


class PlcEnvironmentNameTakenError(ConflictError):
    """Another live PLC environment already has this name."""


class PlcTagInvalidError(InvalidInputError):
    """A tag name typed by hand holds more than letters, digits and
    underscores, or a manual tag's address or comment breaks a rule."""


class PlcManualTagNotFoundError(NotFoundError):
    pass


class PlcSignalNotFoundError(NotFoundError):
    """A device has no component or signal at the given place."""


class PlcEnvironmentDefaultError(ConflictError):
    """The default PLC environment cannot be archived, and an archived one
    cannot become the default; make another one the default first."""


class ProductDeviceNotFoundError(NotFoundError):
    pass


class ProductDeviceNameInvalidError(InvalidInputError):
    """A device name or location is empty where it must not be, or holds a
    character that cannot appear in a file name or has no ASCII form."""


class ProductDeviceNameTakenError(ConflictError):
    """Another device of the same product already has this name, in UTF-8
    or, compared case-insensitively, in ASCII."""


class ProductDeviceReferenceInvalidError(InvalidInputError):
    """A device points at something it may not use: a position or parameter
    of another kind, an archived list entry or kind for a new choice, an
    option of the wrong category, or a file of another product."""


class ProductDeviceEplanTagTakenError(ConflictError):
    """Another component of the same product already carries this EPLAN
    tag."""


class ProductVariantInvalidError(InvalidInputError):
    """A product's variant list has an empty, overlong or repeated name, or
    names a variant of another product."""


# ── Projects ──────────────────────────────────────────────────────────


class ProjectNotFoundError(NotFoundError):
    pass


class ProjectAlreadyExistsError(ConflictError):
    pass


class ProjectInactiveError(ConflictError):
    pass


class ProjectDeleteBlockedError(ConflictError):
    """The project still has lots, production orders, order lines or demands
    that are not finished, and a project with live work is not deleted. The
    message counts them."""


class ProjectStatusMoveBlockedError(ConflictError):
    """The project's status cannot move to the requested one: the move does
    not start from the project's status, or the project still has live work
    that completing or archiving it needs finished. The message says which,
    with the counts."""


class ProjectNumberPatternError(InvalidInputError):
    pass


class ProjectProductRequiredError(InvalidInputError):
    """A project was saved without a product while headless projects are disabled."""

    pass


# ── Attached files ────────────────────────────────────────────────────


class ProductFileNotFoundError(NotFoundError):
    pass


class ProductFileInvalidTypeError(UnsupportedFileTypeError):
    pass


class ProductFileTooLargeError(PayloadTooLargeError):
    pass


# ── Contact links ─────────────────────────────────────────────────────


class ContactLinkInvalidError(InvalidInputError):
    """A link names a contact that does not exist, or an archived contact,
    which is no longer offered for new links."""


class ContactAlreadyLinkedError(ConflictError):
    """The contact is linked to the product or project already, or a
    project's product links it, so the project inherits it."""


class ContactLinkNotFoundError(NotFoundError):
    pass


class InheritedContactLinkError(ConflictError):
    """A project's inherited contact was unlinked at the project. It is the
    product's link; the project mutes it instead."""


# ── Meetings ──────────────────────────────────────────────────────────


class MeetingNotFoundError(NotFoundError):
    pass


class MeetingInvalidInputError(InvalidInputError):
    """A meeting, card, decision, todo or attendee breaks a rule: no owner
    or two, an empty or overlong text, an end before the start, an attendee
    without the person it names, or a reference to something of another
    meeting."""


class MeetingReadOnlyError(ConflictError):
    """The meeting is marked invalid, so its notes are read only until a
    manager restores it."""


class MeetingValidityError(ConflictError):
    """A meeting marked invalid was marked again, or a valid one restored."""


class MeetingCardNotFoundError(NotFoundError):
    pass


class MeetingCardRevisionNotFoundError(NotFoundError):
    pass


class MeetingDecisionNotFoundError(NotFoundError):
    pass


class MeetingTodoNotFoundError(NotFoundError):
    pass


class MeetingAttendeeNotFoundError(NotFoundError):
    pass


class MeetingFileNotFoundError(NotFoundError):
    pass


class MeetingFileInvalidTypeError(UnsupportedFileTypeError):
    pass


class MeetingFileTooLargeError(PayloadTooLargeError):
    pass


class MeetingNotesOutdatedError(ConflictError):
    """The notes a PDF was built from changed since: a card it contains was
    changed, added or deleted, or the issue it carries moved. The browser
    builds the PDF again."""


class MeetingSnapshotNotFoundError(NotFoundError):
    pass


class MeetingNotesDraftNotFoundError(NotFoundError):
    """No draft of meeting notes with this id exists, or it belongs to
    another user, who alone sees it."""
