"""The domain errors of Catalogue.

Each error inherits a semantic base from Platform's domain/exceptions.py,
which the exception handler maps to an HTTP status. The response carries
the class name as its `code`, which clients and translations match on, so
an error keeps its name once it has shipped."""

from src.modules.platform.domain.exceptions import BadRequestError
from src.modules.platform.domain.exceptions import ConflictError
from src.modules.platform.domain.exceptions import InvalidInputError
from src.modules.platform.domain.exceptions import NotFoundError
from src.modules.platform.domain.exceptions import PayloadTooLargeError
from src.modules.platform.domain.exceptions import UnsupportedFileTypeError

# ── Customers ─────────────────────────────────────────────────────────


class CustomerNotFoundError(NotFoundError):
    pass


class CustomerAlreadyExistsError(ConflictError):
    pass


# ── Contacts ──────────────────────────────────────────────────────────


class ContactNotFoundError(NotFoundError):
    pass


class ContactOrganisationInvalidError(InvalidInputError):
    """A contact named both a customer and a supplier, or an organisation
    that does not exist."""


class ContactMailFlagsInvalidError(InvalidInputError):
    """The request and order mail flags were set on a contact that does not
    belong to a supplier."""


class ContactAnonymisedError(ConflictError):
    """An anonymised contact was edited or restored. Its personal data is
    gone for good, so it stays as it is."""


# ── Products and product families ─────────────────────────────────────


class ProductFamilyNotFoundError(NotFoundError):
    pass


class ProductFamilyAlreadyExistsError(ConflictError):
    pass


# ── Suppliers ─────────────────────────────────────────────────────────


class SupplierNotFoundError(NotFoundError):
    pass


class SupplierAlreadyExistsError(ConflictError):
    pass


# ── Labeled entities ──────────────────────────────────────────────────


class LabelTranslationConflictError(ConflictError):
    """A live article group, source item type, fabrication method or
    inspection method already carries the same name in one of the languages
    of the one being saved."""


# ── Article groups ────────────────────────────────────────────────────


class ArticleGroupNotFoundError(NotFoundError):
    pass


# ── Source item types ─────────────────────────────────────────────────


class SourceItemTypeNotFoundError(NotFoundError):
    pass


# ── Fabrication methods ───────────────────────────────────────────────


class FabricationMethodNotFoundError(NotFoundError):
    pass


class FabricationMethodArchivedError(ConflictError):
    pass


class FabricationMethodAssemblyDefaultConflictError(ConflictError):
    """Another fabrication method became the default for assemblies at the
    same moment. The use cases move the flag before saving, so this only
    turns a concurrent write into a 409 instead of an IntegrityError."""

    pass


# ── Inspection methods ────────────────────────────────────────────────


class InspectionMethodNotFoundError(NotFoundError):
    pass


class InspectionMethodArchivedError(ConflictError):
    pass


class InspectionMethodConfigurationError(BadRequestError):
    pass


# ── Bought items ──────────────────────────────────────────────────────


class BoughtItemNotFoundError(NotFoundError):
    pass


class BoughtItemInactiveError(ConflictError):
    pass


class BoughtItemPartNumberNotEditableError(ConflictError):
    pass


class BoughtItemPartNumberDuplicateError(ConflictError):
    pass


class BoughtItemGtinDuplicateError(ConflictError):
    pass


# ── Source items ──────────────────────────────────────────────────────


class SourceItemNotFoundError(NotFoundError):
    pass


class SourceItemInactiveError(ConflictError):
    pass


class SourceItemDuplicateSpecError(ConflictError):
    pass


class MaterialSourceConflictError(BadRequestError):
    pass


# ── Made items and their processes ────────────────────────────────────


class MadeItemNotFoundError(NotFoundError):
    pass


class MadeItemInactiveError(ConflictError):
    pass


class MadeItemPartNumberNotEditableError(ConflictError):
    pass


class MadeItemPartNumberDuplicateError(ConflictError):
    pass


class MadeItemProcessNotFoundError(NotFoundError):
    pass


class MadeItemProcessReorderMismatchError(BadRequestError):
    pass


class MadeItemProcessGroupingInvalidError(InvalidInputError):
    pass


class MadeItemCustomerDataInvalidError(InvalidInputError):
    """Customer data without a customer, or a customer without the
    customer's part number."""


# ── Made-item revisions and the part-number registry ──────────────────


class RevisionNotIncrementableError(ConflictError):
    """The current revision is neither purely numeric nor purely upper-case
    letters, or contains a letter the skip-ambiguous-letters setting
    excludes, so no next revision exists."""


class MadeItemNotNewestRevisionError(ConflictError):
    """An edit targeted an older revision while only the newest revision is
    editable. Status-only changes are exempt."""


class MadeItemRevisionManagedByPdmError(ConflictError):
    """New revisions of a CAD item only come from PDM."""


class MadeItemFieldRequiresRevisionError(ConflictError):
    """The revision policy requires a new revision to change these fields
    on a WEB item. Carries the blocked field names."""


class PartNumberInUseError(ConflictError):
    """The part number belongs to another item or kind. Part numbers are
    unique app-wide, and archived rows keep theirs."""


class WebCreationDisabledError(ConflictError):
    """Web creation of this item kind is off while the PDM integration is
    enabled, so such items come from PDM ingest."""


class PartNumberReservedForPdmError(ConflictError):
    """A typed part number matches the PDM pattern, a number space reserved
    for PDM ingest while the integration is enabled."""


class PdmOwnedFieldReadOnlyError(ConflictError):
    """A caller other than the system user changed a PDM-owned field on a
    CAD row while ownership is enforced. Carries the blocked field names."""


class PdmSuccessorRequiresReplacedStatusError(ConflictError):
    """A successor was set on an enforced PDM-owned row whose status is not
    `replaced`. Status is PDM-owned there, so the file must reach a
    replaced workflow state in PDM first. Clearing a successor is allowed."""


# ── Catalogue status and successors ───────────────────────────────────


class CatalogueSuccessorNotFoundError(NotFoundError):
    """The successor a catalogue item names does not exist in its catalogue."""


class CatalogueStatusChangeError(ConflictError):
    """A catalogue item's status and successor do not fit together: a
    replaced item needs a successor that exists, is not archived and does not
    lead back to it, and only a replaced item names one."""


# ── Order items and deliveries ────────────────────────────────────────


class DeliveryToleranceInvalidError(InvalidInputError):
    """A delivery tolerance is not a finite percentage from 0 to 100."""


# ── Machines, calendars and scheduling ────────────────────────────────


class ProductionMachineNotFoundError(NotFoundError):
    pass


class MachineCapabilityMismatchError(InvalidInputError):
    pass


# ── Attached files ────────────────────────────────────────────────────


class BoughtItemFileNotFoundError(NotFoundError):
    pass


class BoughtItemFileInvalidTypeError(UnsupportedFileTypeError):
    pass


class BoughtItemFileTooLargeError(PayloadTooLargeError):
    pass


class MadeItemFileNotFoundError(NotFoundError):
    pass


class MadeItemFileInvalidTypeError(UnsupportedFileTypeError):
    pass


class MadeItemFileTooLargeError(PayloadTooLargeError):
    pass


class SourceItemFileNotFoundError(NotFoundError):
    pass


class SourceItemFileInvalidTypeError(UnsupportedFileTypeError):
    pass


class SourceItemFileTooLargeError(PayloadTooLargeError):
    pass


class ItemPictureNotFoundError(NotFoundError):
    pass


class ItemPictureInvalidTypeError(UnsupportedFileTypeError):
    pass


class ItemPictureTooLargeError(PayloadTooLargeError):
    pass


# ── EPLAN Data Portal ─────────────────────────────────────────────────


class SupplierEdpCodeInvalidError(BadRequestError):
    """A supplier's Data Portal code is not a short manufacturer code."""


class SupplierEdpCodeInUseError(ConflictError):
    """Another live supplier already carries this Data Portal code."""


# ── Spreadsheet data import ───────────────────────────────────────────


class DataImportSettingsInvalidError(BadRequestError):
    """An import profile breaks a rule of data_import_profiles.validate_profile:
    a header row, data offset or row limit out of range, an unknown field,
    an empty or overlong column name, or one name mapped to two fields."""


class DataImportRowLimitExceededError(BadRequestError):
    """A batch validate or commit request holds more rows than the import's
    profile allows."""
