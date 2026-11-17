"""
Turns a template's copies_rule into an actual number of copies for one
auto-print occurrence. Manual prints do not come through here: they either
carry an explicit `copies` from the caller or fall back to copies_fixed
(see PrintDocument.execute), because a person clicking Print is choosing a
count, not deriving one from a lifecycle moment.

Quantities are floats (kg and m are plausible units), so the two
quantity-derived rules truncate: a delivery of 2.5 prints 2 labels, not 3.
A rule that cannot be resolved (no quantity on the moment, no lot behind
the root) degrades to copies_fixed rather than failing the print; the
job still has to reach the printer.

The result is deliberately NOT clamped here. PrintDocument.execute owns
the `max(1, min(copies, max_copies))` bound so that manual and auto prints
are capped by exactly the same line of code.
"""

from pydantic import BaseModel

from src.modules.quality.application.services.print_classifiers import TriggerSpec
from src.modules.quality.domain.entities.print_template import PrintTemplate
from src.modules.quality.domain.value_objects.print_classifier import PrintCopiesRule
from src.shared_kernel.domain.events.base import DomainEvent


def resolve_auto_print_copies(
    template: PrintTemplate,
    spec: TriggerSpec,
    event: DomainEvent,
    root: BaseModel | None,
) -> int:
    """`root` is only consulted for PER_LOT_QUANTITY, so the caller can
    skip resolving it entirely for the other rules."""
    if template.copies_rule == PrintCopiesRule.PER_EVENT_QUANTITY.value:
        if spec.event_quantity_from is None:
            return template.copies_fixed
        return int(spec.event_quantity_from(event))

    if template.copies_rule == PrintCopiesRule.PER_LOT_QUANTITY.value:
        quantity = getattr(root, "quantity", None)
        if not isinstance(quantity, int | float):
            return template.copies_fixed
        return int(quantity)

    return template.copies_fixed
