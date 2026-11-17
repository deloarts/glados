import pytest

from src.modules.workspace.domain.entities.product_variant import ProductVariant
from src.modules.workspace.domain.errors import ProductVariantInvalidError
from src.modules.workspace.domain.services.product_variant_rules import VariantDraft
from src.modules.workspace.domain.services.product_variant_rules import sync_variants


def _variant(id: int, name: str, sort_order: int = 0) -> ProductVariant:
    return ProductVariant(id=id, product_id=1, name=name, sort_order=sort_order)


def test_sync_variants_orders_renames_adds_and_archives() -> None:
    existing = [_variant(1, "Clamp 60", 0), _variant(2, "Clamp 80", 1), _variant(3, "Old", 2)]
    result = sync_variants(
        1,
        existing,
        [VariantDraft(2, "  Clamp   80 "), VariantDraft(None, "Clamp 100"), VariantDraft(1, "C60")],
    )
    live = [(v.id, v.name, v.sort_order) for v in result if not v.archived]
    assert live == [(2, "Clamp 80", 0), (0, "Clamp 100", 1), (1, "C60", 2)]
    assert [v.id for v in result if v.archived] == [3]


def test_sync_variants_restores_an_archived_variant() -> None:
    old = _variant(1, "Clamp 60")
    old.archived = True
    result = sync_variants(1, [old], [VariantDraft(1, "Clamp 60")])
    assert [v.archived for v in result] == [False]


@pytest.mark.parametrize(
    "drafts",
    [
        [VariantDraft(None, "   ")],
        [VariantDraft(None, "x" * 101)],
        [VariantDraft(None, "Clamp"), VariantDraft(None, "CLAMP")],
        [VariantDraft(99, "Foreign")],
    ],
)
def test_sync_variants_rejects_invalid_lists(drafts: list[VariantDraft]) -> None:
    with pytest.raises(ProductVariantInvalidError):
        sync_variants(1, [_variant(1, "Clamp 60")], drafts)
