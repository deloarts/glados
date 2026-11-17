"""
Content-type validation of order file uploads: every document category,
including the invoice category, accepts PDFs only; pictures accept the
image types and nothing else.
"""

import pytest

from src.modules.fulfillment.application.use_cases.order.upload_order_file import _validate
from src.modules.fulfillment.domain.errors import OrderFileInvalidTypeError
from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory

_DOCUMENT_CATEGORIES = [c for c in OrderFileCategory if c is not OrderFileCategory.PICTURE]


class TestValidate:
    @pytest.mark.parametrize("category", _DOCUMENT_CATEGORIES)
    def test_document_categories_accept_pdf(self, category):
        assert _validate(category, "application/pdf") == ".pdf"

    @pytest.mark.parametrize("category", _DOCUMENT_CATEGORIES)
    def test_document_categories_reject_images(self, category):
        with pytest.raises(OrderFileInvalidTypeError):
            _validate(category, "image/png")

    def test_invoice_is_a_document_category(self):
        assert OrderFileCategory.INVOICE in _DOCUMENT_CATEGORIES

    def test_picture_accepts_images_and_rejects_pdf(self):
        assert _validate(OrderFileCategory.PICTURE, "image/jpeg") == ".jpg"
        with pytest.raises(OrderFileInvalidTypeError):
            _validate(OrderFileCategory.PICTURE, "application/pdf")
