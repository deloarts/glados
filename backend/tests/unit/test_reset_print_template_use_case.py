"""
Unit tests for ResetPrintTemplate.
`POST /print-templates/{classifier}/reset` has no integration test either,
so this is the use case's only coverage.

Reuses make_actor/make_label_template/FakePrintTemplateRepository from
tests/unit/test_update_print_template_clearable_fields.py, the sibling
module that already builds these for the same entity/permission.
"""

import pytest

from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.quality.application.use_cases.print_template.reset_print_template import (
    ResetPrintTemplate,
)
from src.modules.quality.domain.errors import PrintTemplateNotFoundError
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.test_update_print_template_clearable_fields import FakePrintTemplateRepository
from tests.unit.test_update_print_template_clearable_fields import make_actor
from tests.unit.test_update_print_template_clearable_fields import make_label_template


class TestResetPrintTemplate:
    async def test_unknown_classifier_is_not_found(self):
        repo = FakePrintTemplateRepository(make_label_template())
        use_case = ResetPrintTemplate(repo, uow=FakeUnitOfWork())

        with pytest.raises(PrintTemplateNotFoundError):
            await use_case.execute(actor=make_actor(), classifier="does_not_exist")

    async def test_requires_write_print_templates(self):
        """The permission check runs after the fetch here (mirroring the
        production code exactly): a wrong classifier is a 404 to everyone,
        a real one still gates on permission for whoever holds it."""
        template = make_label_template()
        template.source = "^XA^FO50,50^FDHello^FS^XZ"
        repo = FakePrintTemplateRepository(template)
        use_case = ResetPrintTemplate(repo, uow=FakeUnitOfWork())
        actor = make_actor()
        actor.permissions = []

        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor=actor, classifier="lot_label")

        # Untouched: the permission error was raised before any mutation.
        assert template.source == "^XA^FO50,50^FDHello^FS^XZ"
        assert template.enabled is True

    async def test_clears_content_fields_but_leaves_trigger_printer_and_auto_print(self):
        template = make_label_template()
        template.source = "^XA^FO50,50^FDHello^FS^XZ"
        template.field_map = {"part_number": "item.part_number"}
        template.design_dpi = 300
        template.label_width_mm = 50.0
        template.label_height_mm = 25.0
        template.paper = "gap"
        repo = FakePrintTemplateRepository(template)
        use_case = ResetPrintTemplate(repo, uow=FakeUnitOfWork())

        result = await use_case.execute(actor=make_actor(), classifier="lot_label")

        assert result.source is None
        assert result.field_map == {}
        assert result.enabled is False
        assert result.design_dpi is None
        assert result.label_width_mm is None
        assert result.label_height_mm is None
        assert result.paper is None
        # Deliberately left alone (see the use case's own docstring/comment):
        # clearing content must not silently unassign the printer or
        # auto-print wiring an admin already configured.
        assert result.trigger == "lot_created"
        assert result.printer_id == 7
        assert result.auto_print is True

        assert result.changes and "Print template content cleared." in result.changes[-1]
