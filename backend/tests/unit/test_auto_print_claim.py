"""
The auto-print claim: a job row in status printing, written under the unique
(classifier, source_event_id) key before anything is sent, decides which of
several deliveries of one event prints. These tests run the real handler and
the real PrintDocument against in-memory fakes; the Postgres race of the same
claim is in tests/pg/test_auto_print_claim_races.py.
"""

import asyncio

import pytest
from pydantic import BaseModel

from src.modules.fulfillment.domain.events.order_events import OrderItemDelivered
from src.modules.quality.application.use_cases.print_document.handle_event_auto_print import (
    HandleEventAutoPrint,
)
from src.modules.quality.application.use_cases.print_document.print_document import PrintDocument
from src.modules.quality.domain.entities.print_job import PrintJob
from src.modules.quality.domain.errors import PrinterUnreachableError
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintSides
from src.modules.quality.ports.outbound.printer_gateway_port import PrintDelivery
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.test_print_document_use_case import FakeDocketRenderer
from tests.unit.test_print_document_use_case import FakePrinterRepository
from tests.unit.test_print_document_use_case import make_printer
from tests.unit.test_print_document_use_case import make_template

EVENT_ID = "1700-0"


class _Root(BaseModel):
    id: int = 5
    status: str = "delivered"


class ClaimingJobRepo:
    """Keeps rows like print_job_table: one per (classifier,
    source_event_id), claimed in status printing and finished in place."""

    def __init__(self) -> None:
        self.rows: dict[int, PrintJob] = {}
        self._next_id = 1

    async def claim_for_event(self, item: PrintJob) -> PrintJob | None:
        if any(
            r.classifier == item.classifier and r.source_event_id == item.source_event_id
            for r in self.rows.values()
        ):
            return None
        item.id = self._next_id
        self._next_id += 1
        self.rows[item.id] = item
        return item

    async def finish_claimed(self, item: PrintJob) -> PrintJob:
        assert item.id in self.rows, "finish of a claim that does not exist"
        self.rows[item.id] = item
        return item

    async def release_claim(self, job_id: int) -> None:
        if job_id in self.rows and self.rows[job_id].status == "printing":
            del self.rows[job_id]

    async def save(self, item: PrintJob) -> PrintJob:
        raise AssertionError("an auto-print must finish its claim, not write a second row")


class ArmedTemplates:
    def __init__(self) -> None:
        template = make_template(classifier=PrintClassifier.SOURCE_ITEM_LABEL)
        template.auto_print = True
        self.template = template

    async def get_armed_by_trigger(self, trigger: str):
        return [self.template] if trigger == self.template.trigger else []

    async def get_by_classifier(self, classifier: str):
        return self.template if classifier == self.template.classifier else None


class Users:
    async def get_by_id(self, id: int):
        return make_user(id=id, username="operator", full_name="Op Erator", permissions=[])


class Roots:
    def __init__(self, raise_once: Exception | None = None) -> None:
        self._raise_once = raise_once

    async def resolve(self, root_type: str, root_id: int):
        if self._raise_once is not None:
            exc, self._raise_once = self._raise_once, None
            raise exc
        return _Root(id=root_id)


class SlowGateway:
    """Yields to the event loop inside send, so a second delivery running
    concurrently gets every chance to slip in between claim and outcome."""

    def __init__(self, raise_on_send: Exception | None = None) -> None:
        self.sent: list[int] = []
        self._raise_on_send = raise_on_send

    async def send(
        self, printer, payload, content_type, copies, *, sides: PrintSides = PrintSides.ONE_SIDED
    ):
        await asyncio.sleep(0)
        if self._raise_on_send:
            raise self._raise_on_send
        self.sent.append(copies)
        return PrintDelivery()


class Worker:
    """One event worker: the handler and PrintDocument over its own unit of
    work, sharing the database (the job repo) with the other workers."""

    def __init__(self, jobs: ClaimingJobRepo, gateway: SlowGateway, roots: Roots) -> None:
        templates = ArmedTemplates()
        self.uow = FakeUnitOfWork()
        self.handler = HandleEventAutoPrint(
            template_repo=templates,  # type: ignore[arg-type]
            job_repo=jobs,
            user_repo=Users(),  # type: ignore[arg-type]
            root_resolver=roots,
            print_document=PrintDocument(
                template_repo=templates,  # type: ignore[arg-type]
                printer_repo=FakePrinterRepository([make_printer(id=1)]),  # type: ignore[arg-type]
                job_repo=jobs,
                root_resolver=roots,
                gateway=gateway,
                docket_renderer=FakeDocketRenderer(),  # type: ignore[arg-type]
                asset_resolver=None,
                domain_url="https://glados.example",
                uow=self.uow,
            ),
            uow=self.uow,
        )


def delivered() -> OrderItemDelivered:
    return OrderItemDelivered(
        order_item_id=5, order_id=2, bought_item_id=None, actor_id=7, source_item_id=5, quantity=1
    )


async def test_two_concurrent_deliveries_print_once():
    jobs = ClaimingJobRepo()
    gateway = SlowGateway()
    first, second = Worker(jobs, gateway, Roots()), Worker(jobs, gateway, Roots())

    await asyncio.gather(
        first.handler.execute(delivered(), EVENT_ID),
        second.handler.execute(delivered(), EVENT_ID),
    )

    assert gateway.sent == [1]
    assert [(r.status, r.source_event_id) for r in jobs.rows.values()] == [("sent", EVENT_ID)]


async def test_the_claim_is_committed_before_the_print_is_sent():
    jobs = ClaimingJobRepo()
    statuses_at_send: list[str] = []

    class PeekingGateway(SlowGateway):
        async def send(self, printer, payload, content_type, copies, **kwargs):
            statuses_at_send.extend(r.status for r in jobs.rows.values())
            return await super().send(printer, payload, content_type, copies, **kwargs)

    worker = Worker(jobs, PeekingGateway(), Roots())
    await worker.handler.execute(delivered(), EVENT_ID)

    assert statuses_at_send == ["printing"]
    assert worker.uow.commits >= 2  # the claim, then the outcome


async def test_a_later_delivery_of_a_printed_event_prints_nothing():
    jobs = ClaimingJobRepo()
    gateway = SlowGateway()

    await Worker(jobs, gateway, Roots()).handler.execute(delivered(), EVENT_ID)
    await Worker(jobs, gateway, Roots()).handler.execute(delivered(), EVENT_ID)

    assert gateway.sent == [1]


async def test_an_unreachable_printer_finishes_the_claim_as_failed_and_is_not_retried():
    jobs = ClaimingJobRepo()
    gateway = SlowGateway(raise_on_send=PrinterUnreachableError("Printer offline."))

    await Worker(jobs, gateway, Roots()).handler.execute(delivered(), EVENT_ID)
    await Worker(jobs, SlowGateway(), Roots()).handler.execute(delivered(), EVENT_ID)

    [row] = jobs.rows.values()
    assert row.status == "failed"
    assert row.error_message == "Printer offline."


async def test_an_error_before_the_send_releases_the_claim_for_the_redelivery():
    jobs = ClaimingJobRepo()
    gateway = SlowGateway()
    worker = Worker(jobs, gateway, Roots(raise_once=RuntimeError("database went away")))

    with pytest.raises(RuntimeError):
        await worker.handler.execute(delivered(), EVENT_ID)

    assert jobs.rows == {}
    assert worker.uow.rollbacks == 1

    # The event bus redelivers the unacknowledged message.
    await worker.handler.execute(delivered(), EVENT_ID)
    assert gateway.sent == [1]
    assert [r.status for r in jobs.rows.values()] == ["sent"]


async def test_an_error_after_the_send_keeps_the_claim():
    jobs = ClaimingJobRepo()
    gateway = SlowGateway()
    worker = Worker(jobs, gateway, Roots())

    async def failing_finish(item: PrintJob) -> PrintJob:
        raise RuntimeError("database went away")

    jobs.finish_claimed = failing_finish  # type: ignore[method-assign]

    with pytest.raises(RuntimeError):
        await worker.handler.execute(delivered(), EVENT_ID)

    # The label is out; the redelivery must not print a second one.
    assert [r.status for r in jobs.rows.values()] == ["printing"]
    await Worker(jobs, gateway, Roots()).handler.execute(delivered(), EVENT_ID)
    assert gateway.sent == [1]
