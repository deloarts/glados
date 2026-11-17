"""
One revision of an inspection checklist. The frontend owns the questions of
each checklist type; this entity keeps what was filled in: the header data,
an answer and a remark per item id, the number of items the type had and
the version of its definition. Counts and verdict are derived from the
answers on every save.

A checklist belongs to a project, to a product, or to nobody, as far as
its type allows (see checklist_type.py). With neither set it is personal
and visible only to its creator (and to holders of manage:checklists).

Its revisions, release, invalid marking and edit lock follow the document
control of controlled_document.py. Only the latest revision can change; an
older one is kept as the record of what was checked back then. Whether a
finished revision needs a release depends on its type (see
checklist_type.py).
"""

from dataclasses import dataclass

from src.modules.quality.domain.entities.controlled_document import ControlledDocument
from src.modules.quality.domain.value_objects.checklist_answer import ChecklistVerdict
from src.modules.quality.domain.value_objects.checklist_type import checklist_type_spec


@dataclass
class Checklist(ControlledDocument):
    # ── Core fields ───────────────────────────────────────────────────
    type: str  # slug from checklist_type.CHECKLIST_TYPES, e.g. "hydraulics"
    title: str
    header: dict[str, str]
    answers: dict[str, str]  # item id → ChecklistAnswer value
    remarks: dict[str, str]  # item id → free text
    definition_version: int
    item_count: int

    # ── Derived from the answers on save ──────────────────────────────
    answered_count: int
    finding_count: int
    verdict: ChecklistVerdict

    # ── Owner (at most one is set; neither means personal) ────────────
    project_id: int | None
    product_id: int | None

    # ── Denormalized (read-only, populated by repository mapper) ──────
    project_number: str | None = None
    product_number: str | None = None

    @property
    def is_personal(self) -> bool:
        return self.project_id is None and self.product_id is None

    @property
    def release_required(self) -> bool:
        spec = checklist_type_spec(self.type)
        return spec.release_required if spec else True

    @property
    def is_complete(self) -> bool:
        return self.answered_count >= self.item_count
