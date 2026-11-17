"""
The checklist types the backend accepts and what each one requires. The
questions themselves live in the frontend, which owns their texts and
translations; the backend only knows the slug, whether a finished
checklist of that type needs a release by a second person, and what a
checklist of that type may belong to. A type that documents a safety
assessment requires a release, a minor type does not. The machinery
checklists assess one machine against the CE requirements, so they belong
to the product that describes it and take its machine data.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

ChecklistOwnerKind = Literal["personal", "project", "product"]


@dataclass(frozen=True)
class ChecklistTypeSpec:
    slug: str
    release_required: bool
    owner_kinds: frozenset[ChecklistOwnerKind]

    def allows_owner(self, kind: ChecklistOwnerKind) -> bool:
        return kind in self.owner_kinds


_PRODUCT_ONLY: frozenset[ChecklistOwnerKind] = frozenset({"product"})


CHECKLIST_TYPES: MappingProxyType[str, ChecklistTypeSpec] = MappingProxyType(
    {
        spec.slug: spec
        for spec in (
            ChecklistTypeSpec(slug="hydraulics", release_required=True, owner_kinds=_PRODUCT_ONLY),
            ChecklistTypeSpec(slug="pneumatics", release_required=True, owner_kinds=_PRODUCT_ONLY),
            ChecklistTypeSpec(slug="robotics", release_required=True, owner_kinds=_PRODUCT_ONLY),
        )
    }
)


def checklist_type_spec(slug: str) -> ChecklistTypeSpec | None:
    return CHECKLIST_TYPES.get(slug)
