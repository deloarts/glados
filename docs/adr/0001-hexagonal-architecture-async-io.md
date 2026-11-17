# 0001 hexagonal backend with async I/O and a sync domain

- Status: accepted
- Date: 2026-10-05

## context

Glados has a large rule set (item ownership, demand coverage, lot status transitions, scheduling) that must stay testable without a database, and several outside systems (PostgreSQL, Redis, SMTP, LDAP, printers, object storage, the PDM Web API) that change independently of those rules. The backend serves many concurrent users and long-lived SSE connections from a few gunicorn workers, so blocking I/O on request threads wasted capacity and held database connections longer than needed.

## decision

The backend is hexagonal: `domain` (entities, services, value objects, events, exceptions) has no framework imports, `application` holds one use case class per action, `ports` declares Protocols for every repository and outside service, and `adapters` implement them. Dependencies point inward only, and `src/bootstrap/main.py` is the single composition root. All I/O from the ports outward is `async def`, on an `AsyncSession` (psycopg 3), `redis.asyncio`, `httpx.AsyncClient` and `aiosmtplib`; blocking libraries and CPU-heavy work are offloaded with `anyio.to_thread`. The domain stays plain synchronous Python. Every ORM relationship is `lazy="raise_on_sql"`, because an implicit lazy load cannot run under an async session.

## consequences

Domain rules are tested with plain unit tests and fakes, and an adapter can be swapped without touching use cases. The price is more files per feature (schema, DTO, use case, mapper, port, repository, model) and an explicit load option for every relationship a read path needs. `lint-imports` and `tests/unit/test_architecture.py` enforce the layering. The rules are in [CONTRIBUTING.md section 1](../CONTRIBUTING.md#1-architecture-in-one-page) and [../reference/development-async.md](../reference/development-async.md).
