"""
Validation and totals of the extra costs a supplier charges beside the line
prices, on an order and on an offer of a quote request alike. An amount is a
positive number of net cents and a discount is subtracted, so a total of
lines and costs is never computed from signed rows the user typed.

A line total counts the lines that are not canceled and carry a price,
price times quantity rounded to whole cents, and is None when no such line
exists, so a page can tell "no prices yet" from a total of zero.
"""

from collections.abc import Collection
from collections.abc import Iterable
from dataclasses import dataclass

from src.modules.fulfillment.domain.errors import ExtraCostInvalidError
from src.modules.fulfillment.domain.value_objects.extra_cost_kind import ExtraCostKind

MAX_LABEL_LENGTH = 120


@dataclass(frozen=True, kw_only=True)
class ExtraCostDraft:
    """One extra cost as a request names it, before it is stored."""

    kind: ExtraCostKind
    amount: int
    label: str | None = None
    note: str | None = None
    line_id: int | None = None


@dataclass(frozen=True, kw_only=True)
class PricedLine:
    """What a line total reads from a line: its price in cents per unit,
    its quantity and whether it was canceled."""

    price: int | None
    quantity: float
    canceled: bool = False


def normalized_label(label: str | None) -> str | None:
    """The label without surrounding blanks, None when nothing is left."""
    stripped = (label or "").strip()
    return stripped or None


def assert_valid_extra_costs(costs: Iterable[ExtraCostDraft], line_ids: Collection[int]) -> None:
    """Refuses an amount that is not positive, a kind that needs a label
    without one, a label longer than MAX_LABEL_LENGTH, and a cost that names
    a line outside `line_ids`, the lines of the order or quote request it is
    written on."""
    for index, cost in enumerate(costs, start=1):
        if cost.amount <= 0:
            raise ExtraCostInvalidError(f"Extra cost {index} needs an amount above zero.")
        label = normalized_label(cost.label)
        if cost.kind.needs_label and label is None:
            raise ExtraCostInvalidError(
                f"Extra cost {index} of kind '{cost.kind.value}' needs a label."
            )
        if label is not None and len(label) > MAX_LABEL_LENGTH:
            raise ExtraCostInvalidError(
                f"The label of extra cost {index} is longer than {MAX_LABEL_LENGTH} characters."
            )
        if cost.line_id is not None and cost.line_id not in line_ids:
            raise ExtraCostInvalidError(
                f"Extra cost {index} names line #{cost.line_id}, which is not on this document."
            )


def signed_amount(kind: str, amount: int) -> int:
    """The amount as it counts towards a total: negative for a discount."""
    return -amount if ExtraCostKind(kind).subtracts else amount


def extra_costs_total(costs: Iterable[tuple[str, int]]) -> int:
    """The sum of (kind, amount) pairs, discounts subtracted."""
    return sum(signed_amount(kind, amount) for kind, amount in costs)


def lines_total(lines: Iterable[PricedLine]) -> int | None:
    """Price times quantity over the priced lines that are not canceled, in
    whole cents, or None when there is no such line."""
    priced = [line for line in lines if line.price is not None and not line.canceled]
    if not priced:
        return None
    return round(sum((line.price or 0) * line.quantity for line in priced))


def net_total(lines: int | None, costs: int, *, has_costs: bool) -> int | None:
    """Lines plus costs, None when neither a priced line nor a cost exists."""
    if lines is None and not has_costs:
        return None
    return (lines or 0) + costs


type CostSummary = tuple[str, int, str | None, str | None, int | None]


def _describe(cost: CostSummary) -> str:
    kind, amount, label, _note, _line = cost
    name = label or kind.replace("_", " ")
    sign = "-" if ExtraCostKind(kind).subtracts else ""
    return f"{name} {sign}{amount / 100:.2f} EUR"


def describe_extra_cost_change(
    before: Iterable[CostSummary], after: Iterable[CostSummary]
) -> str | None:
    """The changelog line for replacing the (kind, amount, label, note,
    line id) rows `before` with `after`, or None when nothing changed."""
    old, new = list(before), list(after)
    if old == new:
        return None
    if not new:
        return "Extra costs removed."
    return "Extra costs set: " + ", ".join(_describe(c) for c in new) + "."
