"""
A flow sequence of a product (machine), such as its automatic cycle, its
homing or its manual mode: the steps the machine runs through and what
each device does in them (see sequence_content.py). It always belongs to
one product, whose devices and variants it uses.

Its revisions, release, invalid marking and edit lock follow the document
control of controlled_document.py. On release the names it shows (devices,
their positions and initial positions, variants) are frozen into
`frozen`, so renaming a device later never changes a released sequence.
"""

from dataclasses import dataclass
from dataclasses import field
from typing import Any

from src.modules.quality.domain.entities.controlled_document import ControlledDocument
from src.modules.quality.domain.value_objects.sequence_content import SequenceStep


@dataclass(kw_only=True)
class Sequence(ControlledDocument):
    product_id: int
    name: str
    steps: list[SequenceStep] = field(default_factory=list)
    # The names the sequence showed when it was released; None before.
    frozen: dict[str, Any] | None = None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    product_number: str | None = None

    @property
    def is_personal(self) -> bool:
        """A sequence always belongs to a product."""
        return False
