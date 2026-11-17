"""
The unfinished work a project still has, which a status move or a delete
of the project checks.
"""

from dataclasses import dataclass
from dataclasses import fields

_LABELS: dict[str, tuple[str, str]] = {
    "lots": ("lot", "lots"),
    "production_orders": ("production order", "production orders"),
    "order_lines": ("order line", "order lines"),
    "bought_demands": ("bought item demand", "bought item demands"),
    "made_demands": ("made item demand", "made item demands"),
    "source_demands": ("source item demand", "source item demands"),
    "quote_requests": ("open quote request", "open quote requests"),
}


@dataclass(frozen=True, kw_only=True)
class ProjectLiveWork:
    """The unfinished work of a project, counted per kind: lots neither
    completed, canceled nor scrapped, production orders neither completed
    nor canceled, order lines neither delivered nor canceled, demands of the
    three families neither fulfilled nor canceled, and quote requests still
    in draft or sent with a line for the project that is neither awarded nor
    dropped."""

    lots: int = 0
    production_orders: int = 0
    order_lines: int = 0
    bought_demands: int = 0
    made_demands: int = 0
    source_demands: int = 0
    quote_requests: int = 0

    @property
    def total(self) -> int:
        return sum(int(getattr(self, f.name)) for f in fields(self))

    def describe(self) -> str:
        """The counts that are not zero, for example "2 lots, 1 order line"."""
        parts = []
        for name, (singular, plural) in _LABELS.items():
            count = int(getattr(self, name))
            if count:
                parts.append(f"{count} {singular if count == 1 else plural}")
        return ", ".join(parts)
