"""The domain errors of Quality & documents.

Each error inherits a semantic base from Platform's domain/exceptions.py,
which the exception handler maps to an HTTP status. The response carries
the class name as its `code`, which clients and translations match on, so
an error keeps its name once it has shipped."""

from src.modules.platform.domain.exceptions import BadRequestError
from src.modules.platform.domain.exceptions import ConflictError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import InvalidInputError
from src.modules.platform.domain.exceptions import NotFoundError
from src.modules.platform.domain.exceptions import PayloadTooLargeError
from src.modules.platform.domain.exceptions import UnsupportedFileTypeError

# ── Flow sequences ────────────────────────────────────────────────────


class SequenceNotFoundError(NotFoundError):
    pass


class SequenceOwnerConflictError(InvalidInputError):
    """Never raised: a sequence always belongs to one product. Kept so the
    sequence kind fills every slot of DocumentAccess."""


class SequenceNotLatestRevisionError(ConflictError):
    pass


class SequenceAlreadyReleasedError(ConflictError):
    pass


class SequenceReleasedError(ConflictError):
    """A released or superseded revision of a sequence cannot change."""


class SequenceNotReleasedError(ConflictError):
    """A new revision starts from a released one."""


class SequenceOfAnotherUserError(InsufficientPermissionsError):
    pass


class SequenceInvalidError(InvalidInputError):
    """A sequence's steps, actions, transitions or conditions break a rule:
    a device, position, step or variant that is not the sequence's own, a
    missing value, or alternative transitions without conditions."""


# ── Calculations ──────────────────────────────────────────────────────


class CalculationNotFoundError(NotFoundError):
    """Also raised for another user's personal calculation, so its existence
    is not revealed."""


class CalculationOwnerConflictError(InvalidInputError):
    """A calculation was given both a project and a product."""


class CalculationReleasedError(ConflictError):
    """A released calculation was edited; changes go through a copy."""


class CalculationNotReleasedError(ConflictError):
    """A new revision was started from a calculation that is not released."""


class CalculationAlreadyReleasedError(ConflictError):
    pass


class CalculationOfAnotherUserError(InsufficientPermissionsError):
    pass


class CalculationNotLatestRevisionError(ConflictError):
    pass


# ── Controlled documents ──────────────────────────────────────────────


class DocumentLockedError(ConflictError):
    """Someone else holds the edit lock of the document, so it cannot be
    changed, released or locked until they finish or their lock runs out."""


class DocumentNotLockedError(ConflictError):
    """A draft is saved only by the person holding its edit lock; their lock
    ran out, was taken over, or was never taken."""


class ReleasedDocumentDeleteError(ConflictError):
    """A released revision is a quality record and is kept; a wrong one is
    marked invalid instead."""


class DocumentNotReleasedError(ConflictError):
    """Only a released revision can be marked invalid; a draft is changed."""


class DocumentAlreadyInvalidError(ConflictError):
    pass


# ── Checklists ────────────────────────────────────────────────────────


class ChecklistNotFoundError(NotFoundError):
    """Also raised for another user's personal checklist, so its existence
    is not revealed."""


class ChecklistOwnerConflictError(InvalidInputError):
    """A checklist was given both a project and a product."""


class ChecklistOwnerNotAllowedError(InvalidInputError):
    """The checklist type does not belong to this kind of owner, such as a
    machinery checklist given to a project or kept personal."""


class ChecklistOwnerLockedError(ConflictError):
    """The owner of a checklist changes only while it has a single, still
    editable revision; later revisions keep the owner of their lineage."""


class ChecklistTypeUnknownError(InvalidInputError):
    pass


class ChecklistInvalidAnswersError(InvalidInputError):
    """An answer value is unknown, or there are more answers than items."""


class ChecklistReadOnlyError(ConflictError):
    """The checklist is released or a newer revision exists; changes go
    through a new revision."""


class ChecklistNotLatestRevisionError(ConflictError):
    pass


class ChecklistAlreadyReleasedError(ConflictError):
    pass


class ChecklistReleaseNotApplicableError(ConflictError):
    """The checklist's type has no release step."""


class ChecklistIncompleteError(ConflictError):
    """Items are unanswered or findings lack a remark, so the checklist
    cannot be released or revised yet."""


class ChecklistOwnReleaseError(InsufficientPermissionsError):
    """A checklist is released by someone other than the creator of that
    revision."""


class ChecklistOfAnotherUserError(InsufficientPermissionsError):
    pass


# ── Printing ──────────────────────────────────────────────────────────


class PrinterNotFoundError(NotFoundError):
    pass


class InvalidPrinterHostError(InvalidInputError):
    """The host is not a printer's host name or address, see printer_host.py."""


class PrinterUnreachableError(BadRequestError):
    """The printer did not respond, or the connection was refused/timed out."""


class PrintRejectedError(BadRequestError):
    """The printer accepted the connection but refused the job (e.g. IPP
    status >= 0x0100)."""


class PrinterKindMismatchError(BadRequestError):
    """A template's output kind does not match the printer's kind, for
    example a PDF docket sent to a ZPL label printer."""


class PrintTemplateNotFoundError(NotFoundError):
    pass


class PrintTemplateNotConfiguredError(BadRequestError):
    """The template row exists but has no source yet, or is disabled:
    there is nothing to render or download."""


class ZplTemplateInvalidError(BadRequestError):
    """The stored ZPL text failed validation: an unmapped placeholder, a
    malformed {seq}-style token, or missing ^XA/^XZ."""


class DocketSpecInvalidError(BadRequestError):
    """The stored docket block-spec JSON failed pydantic validation."""


class PrintRootNotFoundError(NotFoundError):
    """The record a print job would render from (order item, production
    order, lot, catalogue item, ...) no longer exists."""


class ScrapTagRecordNotFoundError(NotFoundError):
    """Raised by the lot-scoped manual scrap tag print action when the lot
    has no completion or delivery record carrying a scrap disposition to
    print from."""


class PrintTriggerInvalidError(BadRequestError):
    """A template was bound to a trigger whose root type does not match the
    template's classifier, or whose event extras don't cover the field map."""


class PrintCopiesRuleInvalidError(BadRequestError):
    """The chosen copies_rule is not one of the classifier's allowed rules
    (e.g. PER_EVENT_QUANTITY on a classifier with no quantity-bearing
    trigger)."""


class PrintFieldMapInvalidError(BadRequestError):
    """A field_map entry names a source that does not exist for this
    classifier/trigger combination."""


class PrintDocumentTooLargeError(PayloadTooLargeError):
    """An uploaded document for printing exceeds the size limit."""


class PrintDocumentInvalidTypeError(UnsupportedFileTypeError):
    """An uploaded document for printing is not a PDF."""


class PrintDocumentKindRefusedError(InvalidInputError):
    """A report kind that its own record journals, such as meeting notes,
    was sent through the general print or download route."""
