"""
UpdatePrintTemplate's docket-spec validation path: a PDF_DOCKET classifier
validates `source` as a block spec (via validate_docket_spec) the same
way a ZPL classifier validates its text.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.application.dto.print_template_dto import UpdatePrintTemplateCommand
from src.modules.quality.application.use_cases.print_template.update_print_template import (
    UpdatePrintTemplate,
)
from src.modules.quality.domain.entities.print_template import PrintTemplate
from src.modules.quality.domain.errors import DocketSpecInvalidError
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintCopiesRule
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

_VALID_DOCKET_SPEC = (
    '{"page": {"width_mm": 40, "height_mm": 40}, '
    '"blocks": [{"type": "text", "x": 2, "y": 2, "size_mm": 4, "field": "part_number"}]}'
)


def make_actor() -> User:
    return make_user(
        username="admin", full_name="Admin User", permissions=[Permission.WRITE_PRINTERS]
    )


def make_docket_template() -> PrintTemplate:
    return PrintTemplate(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        classifier=PrintClassifier.MADE_ITEM_DOCKET,
        trigger=None,
        source=None,
        field_map={},
        printer_id=None,
        auto_print=False,
        copies_rule=PrintCopiesRule.FIXED,
        copies_fixed=1,
        max_copies=50,
        paper="a4",
        enabled=False,
        note=None,
        creator_id=None,
    )


class FakePrintTemplateRepository:
    def __init__(self, template: PrintTemplate):
        self._template = template

    async def get_by_classifier(self, classifier: str):
        return self._template if self._template.classifier == classifier else None

    async def save(self, item: PrintTemplate) -> PrintTemplate:
        self._template = item
        return item


class FakePrinterRepository:
    async def get_by_id(self, id: int):
        return None


class TestUpdatePrintTemplateDocketValidation:
    async def test_valid_docket_spec_is_accepted(self):
        use_case = UpdatePrintTemplate(
            FakePrintTemplateRepository(make_docket_template()),
            FakePrinterRepository(),
            uow=FakeUnitOfWork(),
        )
        cmd = UpdatePrintTemplateCommand(
            source=_VALID_DOCKET_SPEC, field_map={"part_number": "part_number"}
        )
        result = await use_case.execute(make_actor(), "made_item_docket", cmd)
        assert result.source == _VALID_DOCKET_SPEC

    async def test_malformed_json_raises_docket_spec_invalid(self):
        use_case = UpdatePrintTemplate(
            FakePrintTemplateRepository(make_docket_template()),
            FakePrinterRepository(),
            uow=FakeUnitOfWork(),
        )
        cmd = UpdatePrintTemplateCommand(source="{not json", field_map={})
        with pytest.raises(DocketSpecInvalidError):
            await use_case.execute(make_actor(), "made_item_docket", cmd)

    async def test_block_field_missing_from_field_map_raises_docket_spec_invalid(self):
        use_case = UpdatePrintTemplate(
            FakePrintTemplateRepository(make_docket_template()),
            FakePrinterRepository(),
            uow=FakeUnitOfWork(),
        )
        cmd = UpdatePrintTemplateCommand(source=_VALID_DOCKET_SPEC, field_map={})
        with pytest.raises(DocketSpecInvalidError):
            await use_case.execute(make_actor(), "made_item_docket", cmd)
