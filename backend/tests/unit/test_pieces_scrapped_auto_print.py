"""
The pieces_scrapped auto-print trigger: PiecesScrapped -> scrap_tag,
root type production_order_completion, root id the event's own
completion_id. Same dispatch mechanics as test_auto_print_handler.py
(TRIGGERS-driven, no per-trigger code in the handler), kept as its own
file rather than added cases there per this effort's file-ownership rule.
"""

from datetime import date

from src.modules.fulfillment.domain.events.lot_events import PiecesScrapped
from src.modules.platform.domain.entities.user import User
from src.modules.quality.application.use_cases.print_document.handle_event_auto_print import (
    HandleEventAutoPrint,
)
from src.modules.quality.domain.entities.print_job import PrintJob
from src.modules.quality.domain.entities.print_template import PrintTemplate
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintCopiesRule
from src.modules.quality.domain.value_objects.print_classifier import PrintTrigger
from tests.factories import make_user


def make_actor(user_id: int = 7) -> User:
    return make_user(id=user_id, username="operator", full_name="Op Erator")


def make_template(classifier: PrintClassifier, trigger: PrintTrigger) -> PrintTemplate:
    return PrintTemplate(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        classifier=classifier,
        trigger=trigger,
        source="^XA^XZ",
        field_map={},
        printer_id=3,
        auto_print=True,
        copies_rule=PrintCopiesRule.FIXED,
        copies_fixed=1,
        max_copies=50,
        enabled=True,
        note=None,
        creator_id=None,
    )


class FakeTemplateRepo:
    def __init__(self, armed: dict[str, list[PrintTemplate]] | None = None):
        self._armed = armed or {}

    async def get_armed_by_trigger(self, trigger: str) -> list[PrintTemplate]:
        return self._armed.get(trigger, [])


class FakeJobRepo:
    """Claims succeed once per (classifier, source_event_id), like the
    unique index the real claim inserts under."""

    def __init__(self, already_printed: set[tuple[str, str]] | None = None):
        self._printed = already_printed or set()

    async def claim_for_event(self, item: PrintJob) -> PrintJob | None:
        key = (item.classifier, item.source_event_id or "")
        if key in self._printed:
            return None
        self._printed.add(key)
        item.id = len(self._printed)
        return item


class FakeUnitOfWork:
    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


class FakeUserRepo:
    def __init__(self, user: User | None):
        self._user = user

    async def get_by_id(self, id: int):
        return self._user if self._user and self._user.id == id else None


class FakeRootResolver:
    async def resolve(self, root_type: str, root_id: int):
        return None


class FakePrintDocument:
    def __init__(self):
        self.calls: list[dict] = []

    async def execute(self, actor, classifier, root_type, root_id, **kwargs):
        self.calls.append(
            {
                "actor": actor,
                "classifier": classifier,
                "root_type": root_type,
                "root_id": root_id,
                **kwargs,
            }
        )


def build_handler(
    armed: dict[str, list[PrintTemplate]] | None = None,
    *,
    already_printed: set[tuple[str, str]] | None = None,
    user: User | None = None,
) -> tuple[HandleEventAutoPrint, FakePrintDocument]:
    printer = FakePrintDocument()
    handler = HandleEventAutoPrint(
        template_repo=FakeTemplateRepo(armed),
        job_repo=FakeJobRepo(already_printed),
        user_repo=FakeUserRepo(user if user is not None else make_actor()),
        root_resolver=FakeRootResolver(),
        print_document=printer,
        uow=FakeUnitOfWork(),
    )
    return handler, printer


def make_event(**overrides) -> PiecesScrapped:
    fields = {
        "lot_id": 1,
        "lot_number": "LOT-26-00003",
        "position_id": 10,
        "production_order_id": 20,
        "quantity": 2.0,
        "reason": "tool_breakage",
        "replacement_lot_id": None,
        "replacement_lot_number": None,
        "actor_id": 7,
        "completion_id": 99,
        **overrides,
    }
    return PiecesScrapped(**fields)


class TestPiecesScrappedAutoPrint:
    async def test_an_armed_scrap_tag_template_prints_from_the_completion(self):
        handler, printer = build_handler(
            {
                PrintTrigger.PIECES_SCRAPPED.value: [
                    make_template(PrintClassifier.SCRAP_TAG, PrintTrigger.PIECES_SCRAPPED)
                ]
            }
        )

        await handler.execute(make_event(), "1700-0")

        assert len(printer.calls) == 1
        call = printer.calls[0]
        assert call["classifier"] == "scrap_tag"
        assert call["root_type"] == "production_order_completion"
        assert call["root_id"] == 99
        assert call["trigger"] == "auto"
        assert call["source_event_id"] == "1700-0"

    async def test_nothing_armed_prints_nothing(self):
        handler, printer = build_handler({})
        await handler.execute(make_event(), "1700-0")
        assert printer.calls == []

    async def test_an_event_without_a_completion_id_is_skipped(self):
        # Legal for an event still in the stream from before completion_id
        # existed; root_id_from returns None, same "does not apply to this
        # occurrence" skip every other trigger already uses.
        handler, printer = build_handler(
            {
                PrintTrigger.PIECES_SCRAPPED.value: [
                    make_template(PrintClassifier.SCRAP_TAG, PrintTrigger.PIECES_SCRAPPED)
                ]
            }
        )
        await handler.execute(make_event(completion_id=None), "1700-0")
        assert printer.calls == []

    async def test_a_redelivered_message_is_not_printed_twice(self):
        handler, printer = build_handler(
            {
                PrintTrigger.PIECES_SCRAPPED.value: [
                    make_template(PrintClassifier.SCRAP_TAG, PrintTrigger.PIECES_SCRAPPED)
                ]
            },
            already_printed={("scrap_tag", "1700-0")},
        )
        await handler.execute(make_event(), "1700-0")
        assert printer.calls == []
