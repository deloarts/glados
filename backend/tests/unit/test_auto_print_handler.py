"""
The auto-print event handler and the copies rules it resolves. No printer
and no real pipeline: FakePrintDocument records what would have been
printed, so these tests are about dispatch (which moments fire which
templates), idempotency (a redelivered message must never print twice) and
copy counts.
"""

from datetime import date

from pydantic import BaseModel

from src.modules.fulfillment.domain.events.lot_events import LotCompleted
from src.modules.fulfillment.domain.events.lot_events import LotCreated
from src.modules.fulfillment.domain.events.order_events import OrderItemDelivered
from src.modules.fulfillment.domain.events.production_order_events import (
    ProductionOrderCompletionRecorded,
)
from src.modules.platform.domain.entities.user import User
from src.modules.quality.application.services.print_classifiers import TRIGGERS
from src.modules.quality.application.services.print_copies import resolve_auto_print_copies
from src.modules.quality.application.use_cases.print_document.handle_event_auto_print import (
    HandleEventAutoPrint,
)
from src.modules.quality.domain.entities.print_job import PrintJob
from src.modules.quality.domain.entities.print_template import PrintTemplate
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintCopiesRule
from src.modules.quality.domain.value_objects.print_classifier import PrintTrigger
from src.modules.workspace.domain.events.project_events import ProjectCreated
from tests.factories import make_user

# ── Helpers ───────────────────────────────────────────────────────────


def make_actor(user_id: int = 7) -> User:
    # Deliberately no PRINT_DOCUMENTS, see the gate test.
    return make_user(id=user_id, username="operator", full_name="Op Erator", permissions=[])


def make_template(
    classifier: PrintClassifier,
    trigger: PrintTrigger,
    *,
    copies_rule: PrintCopiesRule = PrintCopiesRule.FIXED,
    copies_fixed: int = 1,
) -> PrintTemplate:
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
        copies_rule=copies_rule,
        copies_fixed=copies_fixed,
        max_copies=50,
        enabled=True,
        note=None,
        creator_id=None,
    )


class _FakeLotRoot(BaseModel):
    id: int = 1
    quantity: float = 12.0


class FakeTemplateRepo:
    """Returns armed templates keyed by trigger, mirroring the real
    get_armed_by_trigger's auto_print/enabled/printer-set filter."""

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
    def __init__(self, root=None):
        self.root = root
        self.calls: list[tuple[str, int]] = []

    async def resolve(self, root_type: str, root_id: int):
        self.calls.append((root_type, root_id))
        return self.root


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
    root=None,
) -> tuple[HandleEventAutoPrint, FakePrintDocument, FakeRootResolver]:
    printer = FakePrintDocument()
    resolver = FakeRootResolver(root)
    handler = HandleEventAutoPrint(
        template_repo=FakeTemplateRepo(armed),
        job_repo=FakeJobRepo(already_printed),
        user_repo=FakeUserRepo(user if user is not None else make_actor()),
        root_resolver=resolver,
        print_document=printer,
        uow=FakeUnitOfWork(),
    )
    return handler, printer, resolver


# ── Dispatch ──────────────────────────────────────────────────────────


class TestDispatch:
    async def test_an_armed_template_prints_with_auto_trigger_and_source_event_id(self):
        handler, printer, _ = build_handler(
            {
                PrintTrigger.LOT_CREATED.value: [
                    make_template(PrintClassifier.LOT_DOCKET, PrintTrigger.LOT_CREATED)
                ]
            }
        )

        await handler.execute(LotCreated(lot_id=42, made_item_id=9, creator_id=7), "1700-0")

        assert len(printer.calls) == 1
        call = printer.calls[0]
        assert call["classifier"] == "lot_docket"
        assert call["root_type"] == "production_lot"
        assert call["root_id"] == 42
        assert call["trigger"] == "auto"
        assert call["source_event_id"] == "1700-0"

    async def test_nothing_armed_prints_nothing(self):
        handler, printer, _ = build_handler({})
        await handler.execute(LotCreated(lot_id=42, made_item_id=9, creator_id=7), "1700-0")
        assert printer.calls == []

    async def test_an_unrelated_event_prints_nothing(self):
        handler, printer, _ = build_handler(
            {
                PrintTrigger.LOT_CREATED.value: [
                    make_template(PrintClassifier.LOT_DOCKET, PrintTrigger.LOT_CREATED)
                ]
            }
        )
        await handler.execute(
            ProjectCreated(project_id=1, project_number="PRJ-1", actor_id=7, designated_user_id=7),
            "1700-0",
        )
        assert printer.calls == []

    async def test_one_event_can_fire_two_different_triggers(self):
        # LotCompleted is both lot_completed (root: the lot) and
        # made_item_completed (root: the item it produced).
        handler, printer, _ = build_handler(
            {
                PrintTrigger.LOT_COMPLETED.value: [
                    make_template(PrintClassifier.LOT_DOCKET, PrintTrigger.LOT_COMPLETED)
                ],
                PrintTrigger.MADE_ITEM_COMPLETED.value: [
                    make_template(PrintClassifier.MADE_ITEM_LABEL, PrintTrigger.MADE_ITEM_COMPLETED)
                ],
            }
        )

        await handler.execute(
            LotCompleted(lot_id=42, lot_number="LOT-1", creator_id=7, made_item_id=9), "1700-0"
        )

        printed = {(c["classifier"], c["root_type"], c["root_id"]) for c in printer.calls}
        assert printed == {
            ("lot_docket", "production_lot", 42),
            ("made_item_label", "made_item", 9),
        }

    async def test_a_bought_delivery_does_not_fire_the_source_item_trigger(self):
        # Both triggers ride one OrderItemDelivered; the populated id is
        # what tells them apart, so a BOUGHT line must not print a raw
        # material label.
        handler, printer, _ = build_handler(
            {
                PrintTrigger.SOURCE_ITEM_DELIVERED.value: [
                    make_template(
                        PrintClassifier.SOURCE_ITEM_LABEL, PrintTrigger.SOURCE_ITEM_DELIVERED
                    )
                ],
                PrintTrigger.BOUGHT_ITEM_DELIVERED.value: [
                    make_template(
                        PrintClassifier.BOUGHT_ITEM_LABEL, PrintTrigger.BOUGHT_ITEM_DELIVERED
                    )
                ],
            }
        )

        await handler.execute(
            OrderItemDelivered(
                order_item_id=5,
                order_id=2,
                bought_item_id=88,
                actor_id=7,
                source_item_id=None,
                quantity=3.0,
            ),
            "1700-0",
        )

        assert [c["classifier"] for c in printer.calls] == ["bought_item_label"]
        assert printer.calls[0]["root_id"] == 88

    async def test_a_missing_actor_skips_rather_than_raising(self):
        handler, printer, _ = build_handler(
            {
                PrintTrigger.LOT_CREATED.value: [
                    make_template(PrintClassifier.LOT_DOCKET, PrintTrigger.LOT_CREATED)
                ]
            },
            user=make_actor(user_id=999),  # not the event's creator_id
        )
        await handler.execute(LotCreated(lot_id=42, made_item_id=9, creator_id=7), "1700-0")
        assert printer.calls == []

    async def test_the_actor_is_the_person_who_caused_the_event(self):
        handler, printer, _ = build_handler(
            {
                PrintTrigger.LOT_CREATED.value: [
                    make_template(PrintClassifier.LOT_DOCKET, PrintTrigger.LOT_CREATED)
                ]
            }
        )
        await handler.execute(LotCreated(lot_id=42, made_item_id=9, creator_id=7), "1700-0")
        assert printer.calls[0]["actor"].id == 7


# ── Idempotency ───────────────────────────────────────────────────────


class TestIdempotency:
    async def test_a_redelivered_message_prints_nothing_the_second_time(self):
        handler, printer, _ = build_handler(
            {
                PrintTrigger.LOT_CREATED.value: [
                    make_template(PrintClassifier.LOT_DOCKET, PrintTrigger.LOT_CREATED)
                ]
            },
            already_printed={("lot_docket", "1700-0")},
        )
        await handler.execute(LotCreated(lot_id=42, made_item_id=9, creator_id=7), "1700-0")
        assert printer.calls == []

    async def test_idempotency_is_per_classifier_not_per_message(self):
        # One event fanning out to two classifiers: a redelivery that
        # already printed one must still not re-print it, while an
        # unprinted sibling is unaffected.
        handler, printer, _ = build_handler(
            {
                PrintTrigger.LOT_COMPLETED.value: [
                    make_template(PrintClassifier.LOT_DOCKET, PrintTrigger.LOT_COMPLETED)
                ],
                PrintTrigger.MADE_ITEM_COMPLETED.value: [
                    make_template(PrintClassifier.MADE_ITEM_LABEL, PrintTrigger.MADE_ITEM_COMPLETED)
                ],
            },
            already_printed={("lot_docket", "1700-0")},
        )

        await handler.execute(
            LotCompleted(lot_id=42, lot_number="LOT-1", creator_id=7, made_item_id=9), "1700-0"
        )

        assert [c["classifier"] for c in printer.calls] == ["made_item_label"]


# ── Copies ────────────────────────────────────────────────────────────


class TestCopiesResolution:
    def test_fixed_uses_copies_fixed(self):
        template = make_template(
            PrintClassifier.LOT_LABEL,
            PrintTrigger.LOT_CREATED,
            copies_rule=PrintCopiesRule.FIXED,
            copies_fixed=4,
        )
        spec = TRIGGERS[PrintTrigger.LOT_CREATED]
        assert resolve_auto_print_copies(template, spec, object(), None) == 4

    def test_per_event_quantity_reads_the_delivered_delta(self):
        template = make_template(
            PrintClassifier.BOUGHT_ITEM_LABEL,
            PrintTrigger.BOUGHT_ITEM_DELIVERED,
            copies_rule=PrintCopiesRule.PER_EVENT_QUANTITY,
        )
        spec = TRIGGERS[PrintTrigger.BOUGHT_ITEM_DELIVERED]
        event = OrderItemDelivered(
            order_item_id=5,
            order_id=2,
            bought_item_id=88,
            actor_id=7,
            source_item_id=None,
            quantity=6.0,
        )
        assert resolve_auto_print_copies(template, spec, event, None) == 6

    def test_per_event_quantity_truncates_a_fractional_quantity(self):
        # 2.5 kg delivered prints 2 labels, not 3: documented behaviour.
        template = make_template(
            PrintClassifier.BOUGHT_ITEM_LABEL,
            PrintTrigger.BOUGHT_ITEM_DELIVERED,
            copies_rule=PrintCopiesRule.PER_EVENT_QUANTITY,
        )
        spec = TRIGGERS[PrintTrigger.BOUGHT_ITEM_DELIVERED]
        event = OrderItemDelivered(
            order_item_id=5,
            order_id=2,
            bought_item_id=88,
            actor_id=7,
            source_item_id=None,
            quantity=2.5,
        )
        assert resolve_auto_print_copies(template, spec, event, None) == 2

    def test_per_event_quantity_reads_a_completion_delta(self):
        template = make_template(
            PrintClassifier.PRODUCTION_ORDER_LABEL,
            PrintTrigger.PRODUCTION_ORDER_COMPLETION_RECORDED,
            copies_rule=PrintCopiesRule.PER_EVENT_QUANTITY,
        )
        spec = TRIGGERS[PrintTrigger.PRODUCTION_ORDER_COMPLETION_RECORDED]
        event = ProductionOrderCompletionRecorded(
            production_order_id=1, lot_position_id=2, quantity_completed=3.0, actor_id=7
        )
        assert resolve_auto_print_copies(template, spec, event, None) == 3

    def test_per_event_quantity_on_a_moment_without_one_falls_back_to_fixed(self):
        template = make_template(
            PrintClassifier.LOT_LABEL,
            PrintTrigger.LOT_CREATED,
            copies_rule=PrintCopiesRule.PER_EVENT_QUANTITY,
            copies_fixed=2,
        )
        spec = TRIGGERS[PrintTrigger.LOT_CREATED]  # carries no quantity
        assert resolve_auto_print_copies(template, spec, object(), None) == 2

    def test_per_lot_quantity_reads_the_resolved_lot(self):
        template = make_template(
            PrintClassifier.LOT_LABEL,
            PrintTrigger.LOT_CREATED,
            copies_rule=PrintCopiesRule.PER_LOT_QUANTITY,
        )
        spec = TRIGGERS[PrintTrigger.LOT_CREATED]
        assert (
            resolve_auto_print_copies(template, spec, object(), _FakeLotRoot(quantity=12.0)) == 12
        )

    def test_per_lot_quantity_without_a_resolvable_root_falls_back_to_fixed(self):
        template = make_template(
            PrintClassifier.LOT_LABEL,
            PrintTrigger.LOT_CREATED,
            copies_rule=PrintCopiesRule.PER_LOT_QUANTITY,
            copies_fixed=5,
        )
        spec = TRIGGERS[PrintTrigger.LOT_CREATED]
        assert resolve_auto_print_copies(template, spec, object(), None) == 5

    async def test_the_handler_passes_the_resolved_copy_count_through(self):
        handler, printer, _ = build_handler(
            {
                PrintTrigger.BOUGHT_ITEM_DELIVERED.value: [
                    make_template(
                        PrintClassifier.BOUGHT_ITEM_LABEL,
                        PrintTrigger.BOUGHT_ITEM_DELIVERED,
                        copies_rule=PrintCopiesRule.PER_EVENT_QUANTITY,
                    )
                ]
            }
        )
        await handler.execute(
            OrderItemDelivered(
                order_item_id=5,
                order_id=2,
                bought_item_id=88,
                actor_id=7,
                source_item_id=None,
                quantity=9.0,
            ),
            "1700-0",
        )
        assert printer.calls[0]["copies"] == 9

    async def test_only_per_lot_quantity_costs_a_root_query(self):
        # Resolving the record for a rule that never reads it would be a
        # query for nothing.
        handler, _, resolver = build_handler(
            {
                PrintTrigger.LOT_CREATED.value: [
                    make_template(PrintClassifier.LOT_LABEL, PrintTrigger.LOT_CREATED)
                ]
            }
        )
        await handler.execute(LotCreated(lot_id=42, made_item_id=9, creator_id=7), "1700-0")
        assert resolver.calls == []

        handler, _, resolver = build_handler(
            {
                PrintTrigger.LOT_CREATED.value: [
                    make_template(
                        PrintClassifier.LOT_LABEL,
                        PrintTrigger.LOT_CREATED,
                        copies_rule=PrintCopiesRule.PER_LOT_QUANTITY,
                    )
                ]
            },
            root=_FakeLotRoot(),
        )
        await handler.execute(LotCreated(lot_id=42, made_item_id=9, creator_id=7), "1700-0")
        assert resolver.calls == [("production_lot", 42)]
