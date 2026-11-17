"""
A saved result of one of the engineering tools (fit calculator, general
tolerances, ...). The tools compute in the browser; this entity only keeps
what the user saw: the tool's inputs and a snapshot of its results, with
the versions of the input shape and of the calculation that produced them,
so a later change to a tool's calculation can be detected on reopening.

A calculation belongs to a project, to a product, or to nobody. With
neither set it is personal and visible only to its creator (and to holders
of manage:calculations). Its revisions, release, invalid marking and edit
lock follow the document control of controlled_document.py: once released
it is read-only, and a change goes through a new revision or a copy.

A calculation of a product, or of a project with a product, may reference
one device of that product. The device's name is frozen into the revision
when it is released.
"""

from dataclasses import dataclass
from typing import Any

from src.modules.quality.domain.entities.controlled_document import ControlledDocument


@dataclass
class Calculation(ControlledDocument):
    # ── Core fields ───────────────────────────────────────────────────
    tool: str  # slug of the frontend tool, e.g. "fit_calculator"
    title: str
    note: str | None
    inputs: dict[str, Any]
    results: dict[str, Any]
    input_version: int
    engine_version: int

    # ── Owner (at most one is set; neither means personal) ────────────
    project_id: int | None
    product_id: int | None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    project_number: str | None = None
    product_number: str | None = None

    # ── Device ────────────────────────────────────────────────────────
    # A device of the owning product (or of the owning project's product)
    # the calculation is about. Only a reference: nothing flows from the
    # device into the calculation.
    product_device_id: int | None = None
    # The device's name with product number as it was when the revision was
    # released, so renaming the device later never changes a released
    # document.
    product_device_name: str | None = None
    # The device's current name with product number, read-only.
    product_device_current_name: str | None = None

    @property
    def device_name(self) -> str | None:
        """The name a reader sees: frozen once released, current before."""
        if self.is_released and self.product_device_name is not None:
            return self.product_device_name
        return self.product_device_current_name

    @property
    def is_personal(self) -> bool:
        return self.project_id is None and self.product_id is None
