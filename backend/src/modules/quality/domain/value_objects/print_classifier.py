"""
A classifier is a fixed, code-defined print slot: what kind of document,
rendered from which record, offered in which context menus. Not
user-creatable, the DB holds exactly one configurable row per classifier
(see print_template_table). A trigger is a fixed lifecycle moment a
template can be bound to for auto-print; which trigger fires which
classifier is a value on the template row, not fixed in code (see
application/services/print_classifiers.py's CLASSIFIERS/TRIGGERS registry
and triggers_for()).
"""

from enum import Enum
from enum import unique


@unique
class PrintOutputKind(str, Enum):
    ZPL = "zpl"
    PDF_DOCKET = "pdf_docket"


@unique
class PrintRootType(str, Enum):
    ORDER = "order"  # the whole order, positions included (order_docket)
    ORDER_ITEM = "order_item"
    PRODUCTION_ORDER = "production_order"
    PRODUCTION_LOT = "production_lot"
    MADE_ITEM = "made_item"
    BOUGHT_ITEM = "bought_item"
    SOURCE_ITEM = "source_item"
    # The two possible sources of a scrap tag's data (see scrap_tag's
    # ClassifierSpec/TriggerSpec in application/services/print_classifiers.py
    # and PrintRootResolver): a scrap event is a fact recorded on a
    # ProductionOrderCompletion (scrapped during production) or an
    # OrderItemDelivery (lost at goods receipt), never on the lot itself;
    # the lot only carries the cumulative total, not one occurrence's
    # reason/date/operator/replacement lot.
    PRODUCTION_ORDER_COMPLETION = "production_order_completion"
    ORDER_ITEM_DELIVERY = "order_item_delivery"
    # A saved tool calculation and a checklist revision, the roots of the
    # uploaded reports (see UploadedPrintDocument). No print template renders
    # from them.
    CALCULATION = "calculation"
    CHECKLIST = "checklist"
    # A meeting of Workspace, the root of its printed, downloaded and sent
    # notes. No print template renders from it.
    MEETING = "meeting"


@unique
class PrintClassifier(str, Enum):
    ORDER_DOCKET = "order_docket"
    SOURCE_ITEM_LABEL = "source_item_label"
    BOUGHT_ITEM_LABEL = "bought_item_label"
    MADE_ITEM_LABEL = "made_item_label"
    PRODUCTION_ORDER_LABEL = "production_order_label"
    LOT_LABEL = "lot_label"
    LOT_DOCKET = "lot_docket"
    SCRAP_TAG = "scrap_tag"
    PRODUCTION_ORDER_DOCKET = "production_order_docket"
    MADE_ITEM_DOCKET = "made_item_docket"
    BOUGHT_ITEM_DOCKET = "bought_item_docket"
    SOURCE_ITEM_DOCKET = "source_item_docket"


@unique
class UploadedPrintDocument(str, Enum):
    # Each value belongs to exactly one root type, see uploaded_document_roots.py.
    """A document the browser renders itself and uploads as a finished PDF,
    rather than one the server renders from a print template. It needs no
    template; the value is stored as the job's classifier."""

    CALCULATION_REPORT = "calculation_report"
    CHECKLIST_REPORT = "checklist_report"
    INSPECTION_REPORT = "inspection_report"
    MEETING_NOTES = "meeting_notes"


@unique
class PrintSides(str, Enum):
    """The IPP `sides` job attribute. Two-sided output is bound on the long
    edge, which is the right binding for the portrait A4 the uploaded
    reports use."""

    ONE_SIDED = "one-sided"
    TWO_SIDED_LONG_EDGE = "two-sided-long-edge"


@unique
class PrintTrigger(str, Enum):
    SOURCE_ITEM_DELIVERED = "source_item_delivered"
    BOUGHT_ITEM_DELIVERED = "bought_item_delivered"
    MADE_ITEM_COMPLETED = "made_item_completed"
    PRODUCTION_ORDER_CREATED = "production_order_created"
    PRODUCTION_ORDER_STARTED = "production_order_started"
    PRODUCTION_ORDER_COMPLETION_RECORDED = "production_order_completion_recorded"
    PRODUCTION_ORDER_COMPLETED = "production_order_completed"
    LOT_CREATED = "lot_created"
    LOT_COMPLETED = "lot_completed"
    PIECES_SCRAPPED = "pieces_scrapped"


@unique
class PrintCopiesRule(str, Enum):
    FIXED = "fixed"
    PER_EVENT_QUANTITY = "per_event_quantity"
    PER_LOT_QUANTITY = "per_lot_quantity"


@unique
class PrintJobStatus(str, Enum):
    # An auto-print claimed by one event delivery and not finished yet. The
    # row is written before the print is sent, so a second delivery of the
    # same event finds it and stays silent; it turns into SENT or FAILED
    # once the printer answered.
    PRINTING = "printing"
    SENT = "sent"
    FAILED = "failed"


@unique
class PrintJobTrigger(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"
