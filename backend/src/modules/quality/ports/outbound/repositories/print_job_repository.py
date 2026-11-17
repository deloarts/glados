"""
Repository interface for PrintJob. Rows are history and are never edited,
with one exception: an auto-print row is written as a claim before its
print is sent and is finished, or released, by the delivery that claimed it.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable

from src.modules.quality.domain.entities.print_job import PrintJob


@dataclass
class PrintJobFilterDto:
    skip: int | None = None
    limit: int | None = None
    classifier: str | None = None
    root_type: str | None = None
    root_id: int | None = None
    printer_id: int | None = None
    status: str | None = None
    order_by: str | None = None
    order_dir: str | None = None


@runtime_checkable
class IPrintJobRepository(Protocol):
    async def save(self, item: PrintJob) -> PrintJob: ...
    async def get_multi(self, filters: PrintJobFilterDto) -> tuple[int, list[PrintJob]]: ...
    async def claim_for_event(self, item: PrintJob) -> PrintJob | None:
        """Writes `item`, an auto-print job in status printing, unless a job
        for the same (classifier, source_event_id) exists, and returns the
        written job, or None when another delivery of the event got there
        first. On Postgres a claim that meets a concurrent uncommitted one
        waits for that transaction to end before it decides."""
        ...

    async def finish_claimed(self, item: PrintJob) -> PrintJob:
        """Stores the outcome of a claimed auto-print (status, resolved
        template, printer and copies, error, rendered output) on the
        claim's row, identified by `item.id`."""
        ...

    async def release_claim(self, job_id: int) -> None:
        """Deletes a claim that is still in status printing, so a later
        delivery of the event can print it. Used only when the print was
        never sent."""
        ...
