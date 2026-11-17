"""
Upload validation for the two newest file slices. Both deliberately carry a
narrower category set than bought/made items (no STEP; source items do
share the MESH singleton with bought/made, products do not), so these also
pin that narrowing: an image category accepts only images, PDF accepts only
application/pdf, and each category has its own size ceiling.

Each file kind's validate_upload is called directly, matching
test_mesh_file_upload_validation.py. It is the whole decision surface, and
reaching it through execute() would require standing up storage.
"""

import pytest

from src.modules.catalogue.application.use_cases.source_item._file_kind import SOURCE_ITEM_FILE_KIND
from src.modules.catalogue.domain.errors import SourceItemFileInvalidTypeError
from src.modules.catalogue.domain.errors import SourceItemFileTooLargeError
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.modules.catalogue.domain.value_objects.source_item_file_category import (
    SourceItemFileCategory,
)
from src.modules.workspace.application.use_cases.product._file_kind import PRODUCT_FILE_KIND
from src.modules.workspace.domain.errors import ProductFileInvalidTypeError
from src.modules.workspace.domain.errors import ProductFileTooLargeError
from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory

MB = 1024 * 1024


# ── Source items ──────────────────────────────────────────────────────


def test_source_items_have_no_image_categories() -> None:
    # A photo of the stock is an ItemPicture, not a file, so an image is
    # refused like any other non-PDF in the PDF slot.
    with pytest.raises(SourceItemFileInvalidTypeError):
        SOURCE_ITEM_FILE_KIND.validate_upload(SourceItemFileCategory.PDF, "image/png", "p.png", 1)


def test_source_pdf_category_accepts_only_pdf() -> None:
    assert (
        SOURCE_ITEM_FILE_KIND.validate_upload(
            SourceItemFileCategory.PDF, "application/pdf", "cert.pdf", 1
        )
        == ".pdf"
    )
    with pytest.raises(SourceItemFileInvalidTypeError):
        SOURCE_ITEM_FILE_KIND.validate_upload(
            SourceItemFileCategory.PDF, "image/png", "cert.png", 1
        )


def test_source_mesh_has_a_higher_ceiling_than_pdf() -> None:
    with pytest.raises(SourceItemFileTooLargeError):
        SOURCE_ITEM_FILE_KIND.validate_upload(
            SourceItemFileCategory.PDF, "application/pdf", "d.pdf", 60 * MB
        )
    # The same size is fine in the MESH slot, whose limit is 100 MB.
    assert SOURCE_ITEM_FILE_KIND.validate_upload(
        SourceItemFileCategory.MESH, "model/stl", "d.stl", 60 * MB
    )


def test_source_items_have_no_step_category() -> None:
    # A source item is raw stock; STEP (an assembly CAD format) exists on
    # bought and made items only. MESH is shared with them, though (a
    # source item can still carry a 3D mesh of the stock shape).
    assert {c.value for c in SourceItemFileCategory} == {"mesh", "pdf"}


# ── Products ──────────────────────────────────────────────────────────


def test_product_image_category_accepts_images() -> None:
    assert (
        PRODUCT_FILE_KIND.validate_upload(ProductFileCategory.THUMBNAIL, "image/png", "p.png", 1)
        == ".png"
    )


def test_product_image_category_rejects_a_pdf() -> None:
    with pytest.raises(ProductFileInvalidTypeError):
        PRODUCT_FILE_KIND.validate_upload(
            ProductFileCategory.THUMBNAIL, "application/pdf", "p.pdf", 1
        )


def test_product_pdf_category_accepts_only_pdf() -> None:
    assert (
        PRODUCT_FILE_KIND.validate_upload(ProductFileCategory.PDF, "application/pdf", "spec.pdf", 1)
        == ".pdf"
    )
    with pytest.raises(ProductFileInvalidTypeError):
        PRODUCT_FILE_KIND.validate_upload(ProductFileCategory.PDF, "text/plain", "spec.txt", 1)


def test_product_image_size_limit_is_enforced() -> None:
    with pytest.raises(ProductFileTooLargeError):
        PRODUCT_FILE_KIND.validate_upload(ProductFileCategory.IMAGE, "image/png", "p.png", 11 * MB)


def test_products_have_no_cad_categories() -> None:
    cad = {
        MadeItemFileCategory.STEP,
        MadeItemFileCategory.MESH,
        MadeItemFileCategory.DRAWING,
        MadeItemFileCategory.DXF,
    }
    assert not {c.value for c in ProductFileCategory} & {c.value for c in cad}


# ── Singleton semantics ───────────────────────────────────────────────


def test_images_are_singletons_and_pdfs_are_not() -> None:
    # Upload replaces a singleton in place; PDFs accumulate.
    assert SourceItemFileCategory.MESH.is_singleton()
    assert not SourceItemFileCategory.PDF.is_singleton()

    assert ProductFileCategory.THUMBNAIL.is_singleton()
    assert ProductFileCategory.IMAGE.is_singleton()
    assert not ProductFileCategory.PDF.is_singleton()
