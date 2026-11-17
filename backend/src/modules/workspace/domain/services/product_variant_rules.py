"""
How a product's variant list follows an edit: names trimmed, non-empty and
unique among the live variants, list order becoming the sort order, and
variants missing from the edit archived rather than deleted. No I/O.
"""

from dataclasses import dataclass

from src.modules.workspace.domain.entities.product_variant import ProductVariant
from src.modules.workspace.domain.errors import ProductVariantInvalidError

NAME_MAX_LENGTH = 100


@dataclass(frozen=True)
class VariantDraft:
    """A variant as an edit sends it; `id` is None for a new one."""

    id: int | None
    name: str


def sync_variants(
    product_id: int, existing: list[ProductVariant], drafts: list[VariantDraft]
) -> list[ProductVariant]:
    by_id = {variant.id: variant for variant in existing}
    names: set[str] = set()
    kept: set[int] = set()
    result: list[ProductVariant] = []
    for index, draft in enumerate(drafts):
        name = " ".join(draft.name.split())
        if not name:
            raise ProductVariantInvalidError("Every variant needs a name.")
        if len(name) > NAME_MAX_LENGTH:
            raise ProductVariantInvalidError(
                f"A variant name is longer than {NAME_MAX_LENGTH} characters."
            )
        if name.casefold() in names:
            raise ProductVariantInvalidError(f"The variant {name!r} appears twice.")
        names.add(name.casefold())
        if draft.id is None:
            result.append(ProductVariant(id=0, product_id=product_id, name=name, sort_order=index))
            continue
        variant = by_id.get(draft.id)
        if variant is None:
            raise ProductVariantInvalidError(f"Variant #{draft.id} is not one of this product's.")
        variant.name = name
        variant.sort_order = index
        variant.archived = False
        kept.add(variant.id)
        result.append(variant)
    for variant in existing:
        if variant.id not in kept:
            variant.archived = True
            result.append(variant)
    return result
