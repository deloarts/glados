"""
The classifier and trigger registries. Two dicts, not two code paths per
classifier: CLASSIFIERS says what a print slot renders from and how, and
TRIGGERS says what a lifecycle moment resolves to and what per-occurrence
data it carries. Which trigger fires which classifier is a value on the
print_template row (see PrintTemplate.trigger), picked from
triggers_for(classifier): the moments whose root matches the classifier's.

Living in the application layer (not domain) because it references DTOs;
the enums it's built from stay in src/modules/quality/domain/value_objects/print_classifier.py.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.catalogue.application.dto.made_item_dto import MadeItemResult
from src.modules.catalogue.application.dto.source_item_dto import SourceItemResult
from src.modules.fulfillment.application.dto.order_dto import OrderItemResult
from src.modules.fulfillment.application.dto.order_dto import OrderResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotResult
from src.modules.fulfillment.application.dto.production_lot_dto import ScrapTagResult
from src.modules.fulfillment.application.dto.production_order_dto import ProductionOrderResult
from src.modules.fulfillment.domain.events.lot_events import LotCompleted
from src.modules.fulfillment.domain.events.lot_events import LotCreated
from src.modules.fulfillment.domain.events.lot_events import PiecesScrapped
from src.modules.fulfillment.domain.events.order_events import OrderItemDelivered
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCompleted
from src.modules.fulfillment.domain.events.production_order_events import (
    ProductionOrderCompletionRecorded,
)
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCreated
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderStarted
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintCopiesRule
from src.modules.quality.domain.value_objects.print_classifier import PrintOutputKind
from src.modules.quality.domain.value_objects.print_classifier import PrintRootType
from src.modules.quality.domain.value_objects.print_classifier import PrintTrigger
from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class RelationSpec:
    """A related record reachable from a resolved root, one or two hops out
    (e.g. project.*, product.* on a production order). Not used by any
    classifier yet; production_order_docket needs ProductionOrder.project_id
    denormalized first (see the printing plan); kept here so wiring it in
    later is a registry entry, not new machinery."""

    name: str
    dto: type[BaseModel]
    id_from: Callable[[Any], int | None]
    via: str | None = None


@dataclass(frozen=True)
class ClassifierSpec:
    output_kind: PrintOutputKind
    root_type: PrintRootType
    default_trigger: PrintTrigger | None  # None = manual only (the 3 catalogue dockets)
    result_dto: type[BaseModel]  # drives the bare field-source list
    copies_rules: tuple[PrintCopiesRule, ...]
    relations: tuple[RelationSpec, ...] = ()

    # Set only for a classifier whose document repeats over a list on its
    # root: currently just order_docket, whose OrderResult carries
    # items[]. row_dto drives the "item.*" field-source namespace, and
    # row_source names the attribute the rows are read from.
    row_dto: type[BaseModel] | None = None
    row_source: str | None = None

    @property
    def has_rows(self) -> bool:
        return self.row_dto is not None and self.row_source is not None


# Key order is the DISPLAY order of the settings tables (see
# GetPrintTemplates, which sorts by it); not the order the rows happen to
# have been inserted in, which would leave a later-added classifier
# stranded at the bottom. Grouped by root, each
# root's label before its docket, following the material-and-production
# flow: stock -> purchased -> manufactured -> the run -> the operation.
# Both settings tabs therefore read the same way in every locale.
# order_docket leads: procurement sits upstream of the stock -> purchased
# -> manufactured flow the rest of this table follows.
CLASSIFIERS: dict[PrintClassifier, ClassifierSpec] = {
    PrintClassifier.ORDER_DOCKET: ClassifierSpec(
        output_kind=PrintOutputKind.PDF_DOCKET,
        root_type=PrintRootType.ORDER,
        default_trigger=None,
        result_dto=OrderResult,
        copies_rules=(PrintCopiesRule.FIXED,),
        row_dto=OrderItemResult,
        row_source="items",
    ),
    PrintClassifier.SOURCE_ITEM_LABEL: ClassifierSpec(
        output_kind=PrintOutputKind.ZPL,
        root_type=PrintRootType.SOURCE_ITEM,
        default_trigger=PrintTrigger.SOURCE_ITEM_DELIVERED,
        result_dto=SourceItemResult,
        copies_rules=(PrintCopiesRule.FIXED, PrintCopiesRule.PER_EVENT_QUANTITY),
    ),
    PrintClassifier.SOURCE_ITEM_DOCKET: ClassifierSpec(
        output_kind=PrintOutputKind.PDF_DOCKET,
        root_type=PrintRootType.SOURCE_ITEM,
        default_trigger=None,
        result_dto=SourceItemResult,
        copies_rules=(PrintCopiesRule.FIXED,),
    ),
    PrintClassifier.BOUGHT_ITEM_LABEL: ClassifierSpec(
        output_kind=PrintOutputKind.ZPL,
        root_type=PrintRootType.BOUGHT_ITEM,
        default_trigger=PrintTrigger.BOUGHT_ITEM_DELIVERED,
        result_dto=BoughtItemResult,
        copies_rules=(PrintCopiesRule.FIXED, PrintCopiesRule.PER_EVENT_QUANTITY),
    ),
    PrintClassifier.BOUGHT_ITEM_DOCKET: ClassifierSpec(
        output_kind=PrintOutputKind.PDF_DOCKET,
        root_type=PrintRootType.BOUGHT_ITEM,
        default_trigger=None,
        result_dto=BoughtItemResult,
        copies_rules=(PrintCopiesRule.FIXED,),
    ),
    PrintClassifier.MADE_ITEM_LABEL: ClassifierSpec(
        output_kind=PrintOutputKind.ZPL,
        root_type=PrintRootType.MADE_ITEM,
        default_trigger=PrintTrigger.MADE_ITEM_COMPLETED,
        result_dto=MadeItemResult,
        copies_rules=(PrintCopiesRule.FIXED,),
    ),
    PrintClassifier.MADE_ITEM_DOCKET: ClassifierSpec(
        output_kind=PrintOutputKind.PDF_DOCKET,
        root_type=PrintRootType.MADE_ITEM,
        default_trigger=None,
        result_dto=MadeItemResult,
        copies_rules=(PrintCopiesRule.FIXED,),
    ),
    PrintClassifier.LOT_LABEL: ClassifierSpec(
        output_kind=PrintOutputKind.ZPL,
        root_type=PrintRootType.PRODUCTION_LOT,
        default_trigger=PrintTrigger.LOT_CREATED,
        result_dto=LotResult,
        copies_rules=(PrintCopiesRule.FIXED, PrintCopiesRule.PER_LOT_QUANTITY),
    ),
    PrintClassifier.LOT_DOCKET: ClassifierSpec(
        output_kind=PrintOutputKind.PDF_DOCKET,
        root_type=PrintRootType.PRODUCTION_LOT,
        default_trigger=PrintTrigger.LOT_CREATED,
        result_dto=LotResult,
        copies_rules=(PrintCopiesRule.FIXED,),
    ),
    # Grouped with the lot classifiers above rather than by its own literal
    # root type (a scrap tag documents one scrap occurrence recorded on a
    # completion or a delivery, not the lot aggregate; see
    # PrintRootType.PRODUCTION_ORDER_COMPLETION/ORDER_ITEM_DELIVERY and
    # PrintRootResolver) because that is where an admin configuring lot
    # printing expects to find it.
    PrintClassifier.SCRAP_TAG: ClassifierSpec(
        output_kind=PrintOutputKind.ZPL,
        root_type=PrintRootType.PRODUCTION_ORDER_COMPLETION,
        default_trigger=PrintTrigger.PIECES_SCRAPPED,
        result_dto=ScrapTagResult,
        copies_rules=(PrintCopiesRule.FIXED,),
    ),
    PrintClassifier.PRODUCTION_ORDER_LABEL: ClassifierSpec(
        output_kind=PrintOutputKind.ZPL,
        root_type=PrintRootType.PRODUCTION_ORDER,
        default_trigger=PrintTrigger.PRODUCTION_ORDER_COMPLETION_RECORDED,
        result_dto=ProductionOrderResult,
        copies_rules=(PrintCopiesRule.FIXED, PrintCopiesRule.PER_EVENT_QUANTITY),
    ),
    PrintClassifier.PRODUCTION_ORDER_DOCKET: ClassifierSpec(
        output_kind=PrintOutputKind.PDF_DOCKET,
        root_type=PrintRootType.PRODUCTION_ORDER,
        default_trigger=PrintTrigger.PRODUCTION_ORDER_CREATED,
        result_dto=ProductionOrderResult,
        copies_rules=(PrintCopiesRule.FIXED,),
    ),
}


@dataclass(frozen=True)
class TriggerSpec:
    """One printable lifecycle moment, described entirely as data so the
    auto-print handler (HandleEventAutoPrint) needs no per-trigger code:
    it walks this table, matches on `event`, and asks the spec for the
    root id, the actor and any per-occurrence quantity."""

    event: type[DomainEvent]  # the domain event class this moment is announced by
    root_type: PrintRootType  # what record the print renders from

    # The record to print, read straight off the event. Returning None
    # means "this moment does not apply to this particular event" and the
    # handler skips it, which is how SOURCE_ITEM_DELIVERED and
    # BOUGHT_ITEM_DELIVERED share one OrderItemDelivered without a guard:
    # a BOUGHT line leaves source_item_id None and vice versa.
    root_id_from: Callable[[Any], int | None]

    # Who caused it. Recorded on print_job.actor_id for attribution, and
    # supplies @actor_full_name; an auto-print is never anonymous.
    actor_id_from: Callable[[Any], int]

    # The quantity of THIS occurrence, when the moment has one (a delivery
    # delta, a completion delta). None = this moment has no such number,
    # which is what makes @event_quantity and the per_event_quantity
    # copies rule unavailable for it.
    event_quantity_from: Callable[[Any], float] | None = None

    @property
    def has_event_quantity(self) -> bool:
        return self.event_quantity_from is not None


TRIGGERS: dict[PrintTrigger, TriggerSpec] = {
    PrintTrigger.SOURCE_ITEM_DELIVERED: TriggerSpec(
        event=OrderItemDelivered,
        root_type=PrintRootType.SOURCE_ITEM,
        root_id_from=lambda e: e.source_item_id,
        actor_id_from=lambda e: e.actor_id,
        event_quantity_from=lambda e: e.quantity,
    ),
    PrintTrigger.BOUGHT_ITEM_DELIVERED: TriggerSpec(
        event=OrderItemDelivered,
        root_type=PrintRootType.BOUGHT_ITEM,
        root_id_from=lambda e: e.bought_item_id,
        actor_id_from=lambda e: e.actor_id,
        event_quantity_from=lambda e: e.quantity,
    ),
    PrintTrigger.MADE_ITEM_COMPLETED: TriggerSpec(
        event=LotCompleted,
        root_type=PrintRootType.MADE_ITEM,
        root_id_from=lambda e: e.made_item_id,
        actor_id_from=lambda e: e.creator_id,
    ),
    PrintTrigger.PRODUCTION_ORDER_CREATED: TriggerSpec(
        event=ProductionOrderCreated,
        root_type=PrintRootType.PRODUCTION_ORDER,
        root_id_from=lambda e: e.production_order_id,
        actor_id_from=lambda e: e.creator_id,
    ),
    PrintTrigger.PRODUCTION_ORDER_STARTED: TriggerSpec(
        event=ProductionOrderStarted,
        root_type=PrintRootType.PRODUCTION_ORDER,
        root_id_from=lambda e: e.production_order_id,
        actor_id_from=lambda e: e.actor_id,
    ),
    PrintTrigger.PRODUCTION_ORDER_COMPLETION_RECORDED: TriggerSpec(
        event=ProductionOrderCompletionRecorded,
        root_type=PrintRootType.PRODUCTION_ORDER,
        root_id_from=lambda e: e.production_order_id,
        actor_id_from=lambda e: e.actor_id,
        event_quantity_from=lambda e: e.quantity_completed,
    ),
    PrintTrigger.PRODUCTION_ORDER_COMPLETED: TriggerSpec(
        event=ProductionOrderCompleted,
        root_type=PrintRootType.PRODUCTION_ORDER,
        root_id_from=lambda e: e.production_order_id,
        actor_id_from=lambda e: e.creator_id,
    ),
    PrintTrigger.LOT_CREATED: TriggerSpec(
        event=LotCreated,
        root_type=PrintRootType.PRODUCTION_LOT,
        root_id_from=lambda e: e.lot_id,
        actor_id_from=lambda e: e.creator_id,
    ),
    PrintTrigger.LOT_COMPLETED: TriggerSpec(
        event=LotCompleted,
        root_type=PrintRootType.PRODUCTION_LOT,
        root_id_from=lambda e: e.lot_id,
        actor_id_from=lambda e: e.creator_id,
    ),
    PrintTrigger.PIECES_SCRAPPED: TriggerSpec(
        event=PiecesScrapped,
        root_type=PrintRootType.PRODUCTION_ORDER_COMPLETION,
        root_id_from=lambda e: e.completion_id,
        actor_id_from=lambda e: e.actor_id,
        event_quantity_from=lambda e: e.quantity,
    ),
}


_PRINTER_KIND_FOR_OUTPUT: dict[PrintOutputKind, str] = {
    PrintOutputKind.ZPL: "zpl_label",
    PrintOutputKind.PDF_DOCKET: "ipp_document",
}


def printer_kind_for(output_kind: PrintOutputKind) -> str:
    """The Printer.kind a template's output_kind requires: the guardrail
    that stops a PDF docket being sent to a raw ZPL socket or vice versa."""
    return _PRINTER_KIND_FOR_OUTPUT[output_kind]


_DISPLAY_ORDER: dict[str, int] = {c.value: i for i, c in enumerate(CLASSIFIERS)}


def display_order_of(classifier: str) -> int:
    """Where this classifier sits in the settings tables. Sorting on this
    rather than on row id keeps the two tabs in a deliberate, stable order
    that is the same in every locale, and stops a classifier added later
    from landing at the bottom. An unknown classifier
    sorts last instead of raising; an ordering concern must never break
    the page."""
    return _DISPLAY_ORDER.get(classifier, len(_DISPLAY_ORDER))


def triggers_for(classifier: PrintClassifier) -> list[PrintTrigger]:
    """The user-selectable moments for this classifier's trigger dropdown:
    every trigger whose root matches. Empty for the three catalogue
    dockets; no trigger has a catalogue-item root, so they stay
    manual-only without any special-casing here."""
    root_type = CLASSIFIERS[classifier].root_type
    return [t for t, spec in TRIGGERS.items() if spec.root_type == root_type]
