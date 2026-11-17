# datetime convention

The rules for storing, comparing and reading datetimes, and for deciding which calendar day an instant falls on. [DEVELOPMENT.md section 8](../DEVELOPMENT.md#8-datetime-convention) gives the summary.

- [datetime convention](#datetime-convention)
  - [1 storing and comparing](#1-storing-and-comparing)
  - [2 reading the current time](#2-reading-the-current-time)
  - [3 the tenant timezone](#3-the-tenant-timezone)
  - [4 production kpis](#4-production-kpis)

## 1 storing and comparing

- Every datetime is stored as UTC and timezone-aware (`DateTime(timezone=True)`, `timestamptz`), never naive.
- Datetimes are compared aware to aware. Never call `.replace(tzinfo=None)` to avoid a mismatch; `tests/unit/test_architecture.py` fails the build if that pattern reappears.
- `as_utc()` in `src/shared_kernel/domain/services/clock.py` normalizes a datetime whose timezone the caller cannot rely on: SQLite, the test database, hands back naive values even for a `DateTime(timezone=True)` column, and an aware value from outside may carry another offset. It reads a naive value as UTC and converts an aware one, so code that compares or converts a loaded datetime works on both dialects. It is not a way around storing aware UTC values.

## 2 reading the current time

- Code reads the current time through `now_utc()` or `today_utc()` from `src/shared_kernel/domain/services/clock.py`, never `datetime.now(UTC)` directly.
- A test that needs a fixed clock replaces the module's `datetime` attribute (`monkeypatch.setattr(clock, "datetime", FrozenClock)`). Every call of both functions reads that attribute, so one patch freezes every caller.

## 3 the tenant timezone

- The whole app uses one timezone: the tenant's default timezone from the general settings (`default_timezone`, seeded as `Europe/Vienna`). There is no per-user timezone.
- Stored instants stay UTC. The tenant zone only decides which calendar day an instant falls on and which wall clock it is shown against.
- Every calendar day the app derives from an instant is a day of that zone. That covers list date filters on the web and `pat` surfaces, "today", number prefixes, printed dates, scheduling days, infoscreens and KPIs.
- Application code reads the zone through `tenant_zone()` (`application/services/scheduling_context.py`) and today through `today_in(zone)`.
- Persistence reads the zone through `read_tenant_zone(db)` and `date_filter_zone(db, ...)` (`persistence/tenant_zone.py`), and today through `tenant_today(db)`.
- An endpoint takes the zone from the `get_tenant_zone` dependency.
- `today_utc()` and the UTC default of `day_start_utc` and `day_after_utc` are not for anything a user sees or filters by.

## 4 production kpis

The production KPIs count every instant on its day in the tenant zone, the same day the schedule's calendars use. That covers a KPI period's bounds, the on-time and late checks, the waiting days and the weekly buckets, so a delivery booked at 00:30 in Vienna counts on that Vienna day.
