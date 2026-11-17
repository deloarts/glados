# async code

The rules for writing async backend code: which code is async, how blocking work leaves the event loop, and what an `AsyncSession` allows. [DEVELOPMENT.md section 10](../DEVELOPMENT.md#10-writing-async-code) gives the summary, and [ADR 0001](../adr/0001-hexagonal-architecture-async-io.md) explains why the backend is async. Paths are relative to `backend/`.

- [async code](#async-code)
  - [1 what is async](#1-what-is-async)
  - [2 exceptions to async ports](#2-exceptions-to-async-ports)
  - [3 blocking work](#3-blocking-work)
  - [4 sessions](#4-sessions)
  - [5 relationship loading](#5-relationship-loading)
  - [6 scheduled work](#6-scheduled-work)

## 1 what is async

- All I/O in the backend is async and the domain stays sync.
- Ports and the adapters behind them are `async def`, apart from the exceptions in [section 2](#2-exceptions-to-async-ports).
- Every use case implements `async def execute(...)`.
- Route handlers, event handlers and scheduled jobs are async.
- No `domain/` package contains `await`.
- Every call to a port or to another use case's async method is awaited.

## 2 exceptions to async ports

- Pure computations stay sync: `ICronSchedule`, `IDocketRenderer`, `IZplRasterizer`, `ISystemStatsReader` and `IStoragePort.get_url`.
- A factory `__call__` that only constructs an object stays sync.
- A lock port's `lock()` returns an async context manager.
- Use-case helpers that touch no port stay sync.
- A callback that does I/O is typed `Callable[..., Awaitable[T]]` and implemented as an `async def`.

## 3 blocking work

- Nothing may block the event loop.
- Libraries without a native async client (boto3, Azure, ldap3, local file I/O, psutil) and CPU-heavy work (bcrypt, Pillow, docket and ZPL rendering, gzip, large scheduling walks) run through `await anyio.to_thread.run_sync(fn, *args)`, with `functools.partial` for keyword arguments.
- A session, an ORM object or any other loop-bound object is never passed into such a thread.
- Where a native async client exists it is used instead: `redis.asyncio`, `httpx.AsyncClient`, `aiosmtplib`, `asyncio.open_connection` and `asyncio.create_subprocess_exec`.

## 4 sessions

A session serves one operation at a time, so `asyncio.gather` over calls that share a session or unit of work is forbidden.

## 5 relationship loading

- Every ORM relationship is `lazy="raise_on_sql"`, because a lazy load cannot happen under an `AsyncSession`.
- Each repository therefore owns a load-options function that every query feeding a mapper applies.
- A write re-reads its row with those options and `populate_existing=True`.
- `User.members` is loaded explicitly in the same way as every other relationship.

## 6 scheduled work

- Scheduled work (backups, the PDM poll, retention purges) runs as interval tasks on each worker's event loop (`src/modules/platform/infrastructure/interval_task.py`), started from the lifespan, not as threads.
- Where only one worker may act on a tick, a Postgres advisory lock decides which one. Backups use the unique `backup_runs.slot` claim instead.
