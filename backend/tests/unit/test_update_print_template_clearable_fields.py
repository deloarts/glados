"""
UpdatePrintTemplate must tell "field omitted from the request" apart from
"field explicitly set to null" for nullable fields like trigger and
printer_id, otherwise the editor dialog's "manual only" trigger option
(value: null) can never actually clear a template's trigger, while a
sparse partial update (e.g. "Disable Auto-Print" sending only
{"auto_print": false}) must still leave every other field untouched. Both
depend on cmd.model_fields_set, which only reflects reality when the
command is built via model_dump(exclude_unset=True). See
print_templates.py's update_print_template endpoint.
"""

from datetime import UTC
from datetime import datetime

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.application.dto.print_template_dto import UpdatePrintTemplateCommand
from src.modules.quality.application.use_cases.print_template.update_print_template import (
    UpdatePrintTemplate,
)
from src.modules.quality.domain.entities.print_template import PrintTemplate
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintCopiesRule
from src.modules.quality.domain.value_objects.print_classifier import PrintTrigger
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork


def make_actor() -> User:
    return make_user(
        username="admin", full_name="Admin User", permissions=[Permission.WRITE_PRINTERS]
    )


def make_label_template() -> PrintTemplate:
    return PrintTemplate(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        classifier=PrintClassifier.LOT_LABEL,
        trigger=PrintTrigger.LOT_CREATED,
        source=None,
        field_map={},
        printer_id=7,
        auto_print=True,
        copies_rule=PrintCopiesRule.FIXED,
        copies_fixed=1,
        max_copies=50,
        note="some note",
        enabled=True,
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


class TestClearableFieldsRespectModelFieldsSet:
    async def test_trigger_explicitly_set_to_none_is_cleared(self):
        template = make_label_template()
        use_case = UpdatePrintTemplate(
            FakePrintTemplateRepository(template), FakePrinterRepository(), uow=FakeUnitOfWork()
        )
        # Simulate the endpoint's model_dump(exclude_unset=True) round trip:
        # only "trigger" was present in the request body.
        cmd = UpdatePrintTemplateCommand.model_validate({"trigger": None})

        result = await use_case.execute(make_actor(), "lot_label", cmd)

        assert result.trigger is None

    async def test_trigger_omitted_from_request_stays_unchanged(self):
        template = make_label_template()
        use_case = UpdatePrintTemplate(
            FakePrintTemplateRepository(template), FakePrinterRepository(), uow=FakeUnitOfWork()
        )
        # Mirrors "Disable Auto-Print": a sparse body with only auto_print.
        cmd = UpdatePrintTemplateCommand.model_validate({"auto_print": False})

        result = await use_case.execute(make_actor(), "lot_label", cmd)

        assert result.auto_print is False
        assert result.trigger == "lot_created"
        assert result.printer_id == 7
        assert result.note == "some note"

    async def test_printer_id_explicitly_set_to_none_is_cleared(self):
        template = make_label_template()
        use_case = UpdatePrintTemplate(
            FakePrintTemplateRepository(template), FakePrinterRepository(), uow=FakeUnitOfWork()
        )
        cmd = UpdatePrintTemplateCommand.model_validate({"printer_id": None})

        result = await use_case.execute(make_actor(), "lot_label", cmd)

        assert result.printer_id is None

    async def test_note_explicitly_set_to_none_is_cleared(self):
        template = make_label_template()
        use_case = UpdatePrintTemplate(
            FakePrintTemplateRepository(template), FakePrinterRepository(), uow=FakeUnitOfWork()
        )
        cmd = UpdatePrintTemplateCommand.model_validate({"note": None})

        result = await use_case.execute(make_actor(), "lot_label", cmd)

        assert result.note is None
