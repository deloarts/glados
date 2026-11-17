"""Where received material comes from and what its paperwork says, as a
delivery records it.

The supplier's batch or heat number, the delivery note and the inspection
certificate (an EN 10204 3.1 one for steel) trace the material from the
receipt to the lot that consumes it. Every part is optional, and a blank one
counts as not given. `damage_noted_on_delivery_note` says whether the
receiver noted damage on the carrier's delivery note at handover, which a
transport damage claim depends on.
"""

from dataclasses import dataclass

MAX_REFERENCE_LENGTH = 100


@dataclass(frozen=True)
class MaterialReceipt:
    supplier_batch: str | None = None
    delivery_note_number: str | None = None
    certificate_reference: str | None = None
    damage_noted_on_delivery_note: bool = False

    def cleaned(self) -> "MaterialReceipt":
        """The receipt with every part trimmed and a blank one left out."""
        return MaterialReceipt(
            supplier_batch=_cleaned(self.supplier_batch),
            delivery_note_number=_cleaned(self.delivery_note_number),
            certificate_reference=_cleaned(self.certificate_reference),
            damage_noted_on_delivery_note=self.damage_noted_on_delivery_note,
        )


def _cleaned(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
