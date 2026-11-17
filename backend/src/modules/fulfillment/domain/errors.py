"""The domain errors of Planning & fulfillment.

Each error inherits a semantic base from Platform's domain/exceptions.py,
which the exception handler maps to an HTTP status. The response carries
the class name as its `code`, which clients and translations match on, so
an error keeps its name once it has shipped."""

from src.modules.platform.domain.exceptions import BadRequestError
from src.modules.platform.domain.exceptions import ConflictError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import InvalidInputError
from src.modules.platform.domain.exceptions import InvalidScheduleCalendarError
from src.modules.platform.domain.exceptions import NotFoundError
from src.modules.platform.domain.exceptions import PayloadTooLargeError
from src.modules.platform.domain.exceptions import UnsupportedFileTypeError

# ── Suppliers ─────────────────────────────────────────────────────────


class OrderSupplierLockedError(ConflictError):
    """An order's supplier was changed although a line of it was already
    ordered from the supplier it names."""


# ── Source items ──────────────────────────────────────────────────────


class SourceItemRequiresReworkStockError(BadRequestError):
    pass


# ── Demand imports ────────────────────────────────────────────────────


class BatchDemandRowInvalidError(InvalidInputError):
    """A row of a demand import no longer matches an item and a project at
    commit, although it did when it was checked; the message names the
    row."""


# ── Demand buckets ────────────────────────────────────────────────────


class BoughtItemDemandBucketNotFoundError(NotFoundError):
    pass


class BoughtItemDemandBucketAlreadyExistsError(ConflictError):
    pass


class MadeItemDemandBucketNotFoundError(NotFoundError):
    pass


class MadeItemDemandBucketAlreadyExistsError(ConflictError):
    pass


class SourceItemDemandBucketNotFoundError(NotFoundError):
    pass


class SourceItemDemandBucketAlreadyExistsError(ConflictError):
    pass


# ── Bought item demands ───────────────────────────────────────────────


class DemandItemNotFoundError(NotFoundError):
    pass


class DemandItemAlreadyFulfilledError(ConflictError):
    pass


class DemandItemAlreadyCanceledError(ConflictError):
    pass


class DemandItemHasAllocationsError(ConflictError):
    """A demand that still holds allocations cannot be deleted; it is
    canceled instead, which releases them."""

    pass


class DemandItemInvalidStatusTransitionError(InvalidInputError):
    pass


class DemandItemInvalidQuantityError(InvalidInputError):
    pass


class DemandItemInvalidAlterationError(InvalidInputError):
    pass


class DemandItemOfAnotherUserError(InsufficientPermissionsError):
    pass


# ── Source item demands ───────────────────────────────────────────────


class SourceItemDemandNotFoundError(NotFoundError):
    pass


class SourceItemDemandAlreadyOrderedError(ConflictError):
    pass


class SourceItemDemandAlreadyCanceledError(ConflictError):
    pass


class SourceItemDemandAlreadyFulfilledError(ConflictError):
    pass


class SourceItemDemandLotStartedError(ConflictError):
    """The raw material demand of a lot that has started production is not
    canceled; the lot's source is switched or the lot force-completed
    instead."""


class SourceItemDemandLotChoiceRequiredError(InvalidInputError):
    """The raw material demand of a lot that has not started is canceled
    only with the caller's choice of whether the lot is canceled with it."""


# ── Orders ────────────────────────────────────────────────────────────


class OrderNotFoundError(NotFoundError):
    pass


class OrderAlreadySubmittedError(ConflictError):
    pass


class OrderAlreadyRequestedError(ConflictError):
    pass


class OrderCannotBeCanceledError(ConflictError):
    pass


class OrderCanceledError(ConflictError):
    """A line was added to, or the header edited on, an order someone
    canceled, which takes no new lines and no further changes."""


class OrderItemCanceledError(ConflictError):
    """A canceled order line was edited; it waits for nothing any more."""


class ExtraCostInvalidError(InvalidInputError):
    """An extra cost on an order or an offer has no positive amount, lacks
    the label its kind needs, or names a line outside its document."""


# ── Quote requests ────────────────────────────────────────────────────


class QuoteRequestNotFoundError(NotFoundError):
    pass


class QuoteRequestLineNotFoundError(NotFoundError):
    pass


class QuoteRequestSupplierNotFoundError(NotFoundError):
    pass


class QuoteRequestNotOpenError(ConflictError):
    """The request was awarded, closed or canceled, so its lines, suppliers
    and offers no longer change."""


class QuoteRequestActionRefusedError(ConflictError):
    """The request's state does not allow the action, such as an award
    without an open line or a cancel after an award."""


class QuoteRequestLineNotOpenError(ConflictError):
    """The line was awarded or dropped, so it takes no change, award or
    removal."""


class QuoteRequestSupplierInUseError(ConflictError):
    """The supplier won a line of the request and stays on it."""


class QuoteRequestSupplierAlreadyAddedError(ConflictError):
    pass


class QuoteRequestInvalidError(InvalidInputError):
    """A line, share, offer or award breaks a rule of the request, such as a
    share for another item, shares beyond the line or an award to a
    supplier who made no offer."""


# ── Order items and deliveries ────────────────────────────────────────


class OrderItemNotFoundError(NotFoundError):
    pass


class OrderItemCannotBeRemovedError(ConflictError):
    pass


class OrderItemCannotBeMovedError(ConflictError):
    pass


class OrderItemCannotBeMarkedError(ConflictError):
    """A line was marked requested or ordered from a status that does not
    allow it: requested only from PENDING, ordered only from PENDING or
    REQUESTED."""


class OrderItemLineTypeMismatchError(InvalidInputError):
    """A field was set on a line type that does not own it, e.g. a
    virtual_name on anything but a VIRTUAL line, or a bought-item
    substitution on a line whose identity comes from another catalogue."""

    pass


class InvalidDeliveryQuantityError(InvalidInputError):
    pass


class OrderItemNotDeliverableError(ConflictError):
    """A delivery was booked on a line that cannot take one: the line is
    not ordered or partially delivered, its order is canceled, or the lot
    behind a MADE line is canceled."""


class DeliveryRejectionInvalidError(InvalidInputError):
    """Raised when a delivery rejects pieces without a reason and outcome,
    or when the accepted-plus-rejected total for the call would exceed
    what the line still has remaining."""

    pass


class OrderItemQuantityBelowDeliveredError(InvalidInputError):
    """An order item's quantity was edited below the pieces already
    delivered or lost on it."""


class OrderItemQuantityNotEditableError(ConflictError):
    """An order item's quantity was edited although the line is no longer
    open: it received pieces, which only closing it short settles, or it is
    canceled."""


class OrderItemCannotBeCanceledError(ConflictError):
    """A line was canceled although its status does not allow it or pieces
    were already delivered or lost on it."""


class OrderItemCannotBeClosedShortError(ConflictError):
    """A line was closed short although it is not ordered or partially
    delivered, or nothing was delivered or lost on it yet."""


class OrderItemReceivedLockedError(ConflictError):
    """A line that already received goods was given another unit, items per
    unit, project or bought item, which would change what was received."""


class OrderItemNotReadyForPickupError(ConflictError):
    """A line was marked ready for pickup although it is not ordered or
    partially delivered, or its order is canceled."""


class PickupInFutureError(InvalidInputError):
    """A line was marked ready for pickup at a time that has not come yet."""


class OrderItemCannotBeReopenedError(ConflictError):
    """A line was reopened although it is not closed short, is a MADE line,
    whose lot closed it, or belongs to a canceled order."""


class OrderItemDeliveryNotFoundError(NotFoundError):
    """A delivery row was named that does not exist on the order line."""


class DeliveryCannotBeCorrectedError(ConflictError):
    """A delivery correction was refused: the line or the row does not allow
    one, or it would take back more than the row accepted."""


# ── Bought item allocations ───────────────────────────────────────────


class AllocationOverflowError(InvalidInputError):
    pass


class OrderItemHoldsRawMaterialError(ConflictError):
    """A line that raw-material demands draw on keeps its bought item: those
    demands take no substitute, so re-pointing the line would hand them
    the wrong material."""


class AllocationTakesArrivedPiecesError(ConflictError):
    """An allocation would take pieces that already arrived for another
    demand on the line: the fill hands arrived pieces out oldest demand
    first, so the other demand would lose them."""


class AllocationItemMismatchError(InvalidInputError):
    pass


class AllocationNotFoundError(NotFoundError):
    pass


class AllocationAlreadyExistsError(ConflictError):
    """A demand already holds an allocation on the order line. A second one
    would replace its quantity, so the existing allocation is changed
    instead."""


class AllocationOrderItemCanceledError(ConflictError):
    """A canceled order line takes no allocation. It keeps its quantity, so
    its free capacity alone would not refuse one."""


# ── Production lots, positions and scrap ──────────────────────────────


class LotNotFoundError(NotFoundError):
    pass


class LotStepNotFoundError(NotFoundError):
    pass


class LotPositionNotFoundError(NotFoundError):
    pass


class LotStructureLockedError(ConflictError):
    pass


class LotPositionGroupingInvalidError(InvalidInputError):
    pass


class LotPositionOverflowError(InvalidInputError):
    pass


class LotInvalidStatusTransitionError(InvalidInputError):
    pass


class LotDemandProjectMismatchError(InvalidInputError):
    pass


class LotDemandMadeItemMismatchError(ConflictError):
    """A lot was to cover a demand for another made item than the one it
    builds."""

    pass


class LotAlterationSourceConflictError(InvalidInputError):
    """A lot's source_made_item_id is a single scalar: raised when its
    demand_allocations mix alteration and non-alteration demands, or
    alteration demands that name different made items to rework."""

    pass


class LotPositionAlreadyAssignedError(ConflictError):
    pass


class LotPositionInUseError(ConflictError):
    """A lot position is still referenced by an order item. The lot rules
    normally reject this earlier; this turns any gap into a 409 instead of
    an IntegrityError."""

    pass


class LotPositionNotAssignableError(ConflictError):
    pass


class LotPositionQuantityExceedsRemainingError(InvalidInputError):
    """An assign call requests more than the position's uncommitted
    remainder."""

    pass


class LotPositionProvisionOverflowError(InvalidInputError):
    pass


class LotRawMaterialAlreadyLinkedError(ConflictError):
    pass


class LotHasOpenDemandError(ConflictError):
    """Switching the source would replace a still-open (not yet ordered)
    source item demand, allowed, but the caller must confirm first."""


class LotHasPlacedDemandError(ConflictError):
    """Switching the source would replace a source item demand already
    allocated or ordered: what arrived stays, the rest is released and
    demanded from the new source. Allowed, but the caller must confirm
    first."""

    pass


class LotHasNoMaterialSourceError(InvalidInputError):
    pass


class LotOnHoldError(ConflictError):
    """Work on a lot that is on hold: a completion, a scrap or the reversal
    of a completion waits until the lot is resumed."""

    pass


class LotNotScrappableError(ConflictError):
    """Scrap targets a terminal lot, or a position without internal work;
    an EXTERNAL position's pieces belong to the supplier."""

    pass


class ScrapQuantityExceedsAvailableError(InvalidInputError):
    """Raised when a scrap quantity exceeds lot_rules.scrap_capacity for
    the targeted position."""

    pass


class ProductionOrderSelectionRequiredError(InvalidInputError):
    """The position has zero or several open production orders and the
    caller did not name one."""

    pass


class SourceApprovalNotPendingError(ConflictError):
    """There is no source approval to decide. Approve also accepts a
    rejected lot, so an approver can override a rejection."""

    pass


class SourceItemApprovalRequiredError(ConflictError):
    """A source item demand was requested while the lot's source approval
    is pending or rejected."""

    pass


# ── Production orders and operators ───────────────────────────────────


class ProductionOrderNotFoundError(NotFoundError):
    pass


class ProductionOrderInvalidStatusTransitionError(InvalidInputError):
    pass


class ProductionOrderInvalidScheduleError(InvalidInputError):
    pass


class ProductionOrderQuantityOverflowError(InvalidInputError):
    pass


class ProductionOrderSplitMismatchError(InvalidInputError):
    pass


class ProductionOrderCannotMergeError(ConflictError):
    pass


class ProductionOrderNotSplittableError(ConflictError):
    pass


class ProductionOrderNoMachineAssignedError(InvalidInputError):
    pass


class ProductionOrderCompletionSplitInvalidError(InvalidInputError):
    pass


class CompletionDateInvalidError(InvalidInputError):
    pass


class CompletionNotFoundError(NotFoundError):
    pass


class CompletionNotReversibleError(ConflictError):
    """A completion that may not be reversed: a reversal itself, one that
    rejected pieces, whose disposition changed the lot, one on a finished
    lot, or one whose pieces the next position already used."""


class CompletionAlreadyReversedError(ConflictError):
    pass


class ProductionOrderMeasurementEvidenceRequiredError(InvalidInputError):
    pass


class ProductionOrderReorderInvalidError(InvalidInputError):
    """A queue-reorder request is malformed (e.g. duplicate ids in the
    ordered list, which would assign a queue_sequence non-uniquely)."""

    pass


class OperatorSelectionRequiredError(InvalidInputError):
    pass


class OperatorNotAssignedError(InvalidInputError):
    pass


class ManufacturingAssessmentNotFoundError(NotFoundError):
    pass


class ManufacturingAssessmentAlreadyExistsError(ConflictError):
    pass


# ── Machines, calendars and scheduling ────────────────────────────────


class ProductionMachineArchiveBlockedError(ConflictError):
    """The machine still has queued, in-progress or paused production orders,
    which archiving would take off the planning and queue boards. The
    message counts them."""


class ProductionMachineArchivedError(ConflictError):
    """An archived machine takes no production order; the order goes to a
    machine still in use, or the machine is restored first."""


class MachinePoolNotFoundError(NotFoundError):
    pass


class MachineWorkingHoursNotFoundError(NotFoundError):
    pass


class MachineCalendarExceptionNotFoundError(NotFoundError):
    pass


class NoWorkingTimeError(InvalidScheduleCalendarError):
    """A calendar has no working time left to place work in, such as a week
    of zero hours or a downtime over the whole search bound. The forward
    walk leaves that machine's queue undated instead of failing."""

    pass


class MachineDowntimeNotFoundError(NotFoundError):
    pass


class MachineAlreadyDownError(ConflictError):
    """The machine already has an open downtime; only one may be open at a time."""


class MachineDowntimeOverlapError(ConflictError):
    """The requested downtime window overlaps an existing downtime on the same machine."""


class MachineDowntimeAlreadyEndedError(ConflictError):
    """The downtime has already ended; correcting its end is an edit, not a second end."""


class InvalidDowntimeRangeError(InvalidInputError):
    """A downtime's ended_at is not strictly after its started_at."""


class AutoPlanRunInProgressError(ConflictError):
    """Another user's Auto-Plan run holds the app-wide mutex. This is a UX
    gate only; the advisory locks in auto_plan.py protect the data."""


# ── Attached files ────────────────────────────────────────────────────


class OrderFileNotFoundError(NotFoundError):
    pass


class OrderFileInvalidTypeError(UnsupportedFileTypeError):
    pass


class OrderFileTooLargeError(PayloadTooLargeError):
    pass


class QuoteRequestFileNotFoundError(NotFoundError):
    pass


class QuoteRequestFileInvalidTypeError(UnsupportedFileTypeError):
    pass


class QuoteRequestFileTooLargeError(PayloadTooLargeError):
    pass


class ProductionOrderFileNotFoundError(NotFoundError):
    pass


class ProductionOrderFileInvalidTypeError(UnsupportedFileTypeError):
    pass


class ProductionOrderFileTooLargeError(PayloadTooLargeError):
    pass
