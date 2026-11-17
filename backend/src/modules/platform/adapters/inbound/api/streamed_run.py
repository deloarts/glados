"""
A long-running use case behind an SSE stream, shared by the Auto-Plan stream
(endpoints/production_schedule.py) and the storage migration stream
(endpoints/admin_settings/storage.py).

FastAPI closes the request's own session before a streaming response sends
its first byte, so the run is an asyncio task that opens its own
`SessionLocal()` and builds its use case from it. The task is held in the
caller's module-level task set, because the event loop only keeps weak
references, and it is never awaited by the request, so a client disconnect
ends the stream but never the run. Frames go onto an unbounded queue that the
SSE generator reads; the closing sentinel None ends the stream.

The caller acquires the run's Redis mutex (a RunRegistry) before it starts the
run, so a loser gets a plain error response and no stream. While the run
works, a heartbeat task refreshes the mutex and persists the progress snapshot
every HEARTBEAT_INTERVAL_S. On the way out the heartbeat is stopped, the mutex
released and the optional end hook awaited, each step guarded on its own, so
one failing step never skips another or masks the queued terminal frame.
"""

import asyncio
import dataclasses
import json
from collections.abc import AsyncIterator
from collections.abc import Awaitable
from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from src.modules.platform.adapters.inbound.api.exception_handlers import mapped_domain_status
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.run_registry import HEARTBEAT_INTERVAL_S
from src.modules.platform.infrastructure.run_registry import RunHandle

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

PING_SECONDS = 15

Frame = dict[str, str]


class StreamedRun[P: "DataclassInstance"]:
    """One stream request's background run with its heartbeat task, own DB
    session and frame queue.

    `execute` builds the use case from the run's session and runs it with
    the progress callback; its result is validated into `response_model`
    for the terminal `result` frame. `snapshot` copies a progress event onto
    the handle for the heartbeat to persist. `label` prefixes every log line
    and the generic failure detail ("<label> failed."), which is all an
    unmapped error reveals, as in domain_error_handler."""

    def __init__(
        self,
        *,
        label: str,
        execute: Callable[[AsyncSession, Callable[[P], None]], Awaitable[object]],
        response_model: type[BaseModel],
        snapshot: Callable[[RunHandle, P], None],
        heartbeat_once: Callable[[RunHandle], Awaitable[object]],
        release: Callable[[RunHandle], Awaitable[object]],
        on_end: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._label = label
        self._execute = execute
        self._response_model = response_model
        self._snapshot = snapshot
        self._heartbeat_once = heartbeat_once
        self._release = release
        self._on_end = on_end
        self._queue: asyncio.Queue[Frame | None] = asyncio.Queue()

    async def start(
        self, handle: RunHandle, tasks: set["asyncio.Task[None]"]
    ) -> EventSourceResponse:
        """Starts the run as a task held in `tasks` and returns the SSE
        response that drains its frames. Releases the mutex when the task
        cannot be created, so a failed start never strands it."""
        try:
            task = asyncio.create_task(self.run(handle))
        except Exception:
            await self._release(handle)
            raise
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        return EventSourceResponse(self._frames(), ping=PING_SECONDS, sep="\n")

    async def _frames(self) -> AsyncIterator[Frame]:
        while True:
            frame = await self._queue.get()
            if frame is None:  # sentinel: the run task is done
                return
            yield frame

    def _put(self, frame: Frame | None) -> None:
        self._queue.put_nowait(frame)

    async def run(self, handle: RunHandle) -> None:
        """Runs the use case, posts exactly one terminal frame, then always
        shuts down."""
        heartbeat = asyncio.create_task(self._heartbeat_loop(handle))
        try:
            async with SessionLocal() as db:
                try:
                    result = await self._execute(db, lambda event: self._on_progress(handle, event))
                    response = self._response_model.model_validate(result, from_attributes=True)
                    self._put({"event": "result", "data": response.model_dump_json()})
                except Exception as exc:
                    await db.rollback()
                    log.exception(f"{self._label} stream run failed")
                    # Only a mapped DomainError echoes its message, as in
                    # domain_error_handler.
                    detail = (
                        str(exc)
                        if mapped_domain_status(exc) is not None
                        else f"{self._label} failed."
                    )
                    self._put({"event": "error", "data": json.dumps({"detail": detail})})
        except Exception:
            log.exception(f"{self._label} stream: session teardown failed")
        finally:
            await self._shut_down(heartbeat, handle)

    async def _heartbeat_loop(self, handle: RunHandle) -> None:
        """Keeps the mutex alive and persists the progress snapshot."""
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)
            try:
                await self._heartbeat_once(handle)
            except Exception:
                log.exception(f"{self._label} stream: heartbeat tick failed")

    def _on_progress(self, handle: RunHandle, event: P) -> None:
        """Posts the SSE frame and updates the in-memory snapshot that the
        heartbeat persists for the status endpoint."""
        self._put({"event": "progress", "data": json.dumps(dataclasses.asdict(event))})
        self._snapshot(handle, event)

    async def _shut_down(self, heartbeat: "asyncio.Task[None]", handle: RunHandle) -> None:
        try:
            heartbeat.cancel()
            await asyncio.wait({heartbeat}, timeout=1.0)
        except Exception:
            log.exception(f"{self._label} stream: heartbeat task stop failed")
        try:
            await self._release(handle)
        except Exception:
            log.exception(f"{self._label} stream: mutex release failed")
        if self._on_end is not None:
            try:
                await self._on_end()
            except Exception:
                log.exception(f"{self._label} stream: end-signal publish failed")
        self._put(None)
