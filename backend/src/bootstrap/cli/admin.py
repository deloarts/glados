"""
Out-of-process recovery commands. Run via the container entrypoint:

    docker compose run --rm backend admin enable-local-login

Or, without a host shell (e.g. a Portainer console into `backend`, or the
`maintenance` sidecar profile if the backend is down): a console/`docker
exec` skips the entrypoint script, so the `admin` shorthand doesn't apply
there, call the module directly instead (see docs/OPERATIONS.md sections
5 and 6):

    poetry run python -m src.bootstrap.cli.admin enable-local-login

These exist for the cases where the UI cannot help because the thing that
is broken is the way in. Access to the container (host shell or a
console such as Portainer's) is the authority, there is no actor and no
permission check, by design, exactly as with `src/bootstrap/cli/restore.py`.
`lifecycle-drift` is the one diagnostic among them: it compares the stored
lifecycle fields with their derivation from the recorded facts and changes
nothing. `lifecycle-repair` writes what that report lists, as the system
user, and only with --apply. `republish-outbox` puts relayed events on the
events stream again after Redis lost them. `pre-migration-dump` is the one the container
entrypoint runs by itself, before it applies pending migrations.

Subcommands live here together rather than as one module each, because
they share the session bootstrap. reset-totp is the only way to reset the
system user's 2FA, since the UI's "Reset 2FA" button is deliberately
unavailable for it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Callable
from collections.abc import Coroutine
from collections.abc import Mapping
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

if TYPE_CHECKING:
    from src.modules.fulfillment.application.services.lifecycle_drift import DriftReport
    from src.modules.fulfillment.application.services.lifecycle_drift import DriftRow
    from src.modules.fulfillment.application.services.lifecycle_repair import RepairReport


async def enable_local_login(_: argparse.Namespace) -> int:
    """Turn password login back on.

    The usual reason to need this: local login was switched off in the
    admin UI and nobody realised it is currently the only interactive
    login method, so the UI is now unreachable. (Signing in as the system
    user also still works, it is exempt from the setting, but that
    requires knowing its password.)
    """
    # Imported inside the command, not at module scope: importing the
    # session builds the settings singleton, so a module-level import would
    # make even `--help` fail when the environment is not configured.
    from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
        SqlAlchemyAdminSettingsRepository,
    )
    from src.modules.platform.adapters.outbound.persistence.session import SessionLocal

    async with SessionLocal() as db:
        repo = SqlAlchemyAdminSettingsRepository(db)
        settings = await repo.get_security()

        if settings.allow_local_login:
            print("Password login is already enabled, nothing to do.", flush=True)
            return 0

        settings.allow_local_login = True
        await repo.save_security(settings)
        await db.commit()

    print("Password login re-enabled.", flush=True)
    return 0


async def disable_ldap(_: argparse.Namespace) -> int:
    """Turn directory authentication back off.

    The usual reason to need this: LDAP was enabled against a misconfigured
    or unreachable directory. Sign in as the system user afterwards, it is
    exempt from directory auth by name and keeps a real local password from
    the deployment's own config.

    **This does not let directory users back in.** Their stored hash is an
    unusable sentinel, so flipping the switch only reroutes them to a local
    password that does not exist; they get the same 401 either way. Fixing
    the directory configuration, not this command, is what restores them.

    Users keep their per-user auth_provider; only the global switch flips, so
    turning LDAP back on restores the previous routing exactly.
    """
    from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
        SqlAlchemyAdminSettingsRepository,
    )
    from src.modules.platform.adapters.outbound.persistence.session import SessionLocal

    async with SessionLocal() as db:
        repo = SqlAlchemyAdminSettingsRepository(db)
        settings = await repo.get_auth()

        if not settings.ldap_enabled:
            print("Directory authentication is already disabled, nothing to do.", flush=True)
            return 0

        settings.ldap_enabled = False
        await repo.save_auth(settings)
        await db.commit()

    print("Directory authentication disabled. All users now sign in locally.", flush=True)
    return 0


async def reset_totp(args: argparse.Namespace) -> int:
    """Clear a user's 2FA enrolment so they can enrol again.

    For a lost authenticator device where nobody with write:settings is
    able to sign in and do it through the UI, or for the system user,
    whose 2FA the UI's "Reset 2FA" button deliberately cannot touch, so
    this command is the only way back for it. Mirrors the UI's own
    administrative reset (application/use_cases/user/reset_user_totp.py):
    clears the secret and revokes every trusted device belonging to the
    user, so a browser that had "trust this device" for the old secret
    cannot skip enrolment of the new one.

    The user is prompted to enrol again at their next login whenever 2FA
    is mandatory for them: enforce_totp is on, they hold write:settings,
    or they are the system user, for whom it is always mandatory.
    Otherwise they simply have 2FA switched off until they set it up
    again.
    """
    from src.modules.platform.adapters.outbound.persistence.repositories.trusted_device_repository import (
        SqlAlchemyTrustedDeviceRepository,
    )
    from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
        SqlAlchemyUserRepository,
    )
    from src.modules.platform.adapters.outbound.persistence.session import SessionLocal

    async with SessionLocal() as db:
        repo = SqlAlchemyUserRepository(db)
        user = await repo.get_by_username(args.username)

        if user is None:
            print(f"No user named {args.username!r}.", file=sys.stderr, flush=True)
            return 1

        if not user.totp_enabled and user.totp_secret is None:
            print(f"{args.username!r} has no 2FA enrolled, nothing to do.", flush=True)
            return 0

        user.totp_secret = None
        user.totp_enabled = False
        await repo.save(user)
        await SqlAlchemyTrustedDeviceRepository(db).revoke_all_for_user(user.id)
        await db.commit()

    print(
        f"2FA reset for {args.username!r}; trusted devices revoked. They re-enrol at "
        "their next login once 2FA is mandatory for them (enforce_totp, write:settings, "
        "or the system user, always).",
        flush=True,
    )
    return 0


async def unlock_users(args: argparse.Namespace) -> int:
    """Release failed-login lockouts.

    With no argument this clears every tracked lockout/counter the shared
    Redis tracker holds, the "we locked ourselves out" button. That is
    login lockouts plus everything else built on the same tracker (the
    TOTP-step throttle, keyed `totp:{user_id}`; the mail send-rate limit,
    keyed `mail:{user_id}`, see login_policy.py / mail_policy.py);
    sweeping all of it is harmless (each is just a counter reset early)
    and keeping this one recovery command simple beats adding one per
    feature. Pass a username to release just that user's *login* throttle
    specifically, its delay and its locks on every address. Address locks
    and the TOTP/mail scopes are not keyed by username, so the single-target
    form cannot address them; use the no-arg form for those.
    """
    from src.modules.platform.adapters.outbound.external.login_attempts.redis_login_attempt_tracker import (
        RedisLoginAttemptTracker,
    )
    from src.modules.platform.application.services.login_throttle import LoginThrottle
    from src.modules.platform.infrastructure.redis_client import get_async_redis_client

    client = get_async_redis_client()
    tracker = RedisLoginAttemptTracker(client)
    try:
        if args.username:
            await LoginThrottle(tracker).release(args.username)
            print(f"Lockout released for {args.username!r}.", flush=True)
            return 0

        removed = await tracker.clear_all()
        print(f"Released {removed} lockout/counter key(s).", flush=True)
        return 0
    finally:
        await client.aclose()


async def replay_dead_letters(args: argparse.Namespace) -> int:
    """Put dead-lettered events back on the events stream.

    An event lands in the dead-letter stream after a consumer group failed
    it five times in a row. Once the cause is fixed (a bug deployed, a
    printer back online, a webhook endpoint reachable again), this puts the
    oldest entries back on the events stream with their original fields
    and removes them from the dead-letter stream. Every consumer group sees
    the replayed event again; groups that already handled it skip it,
    because their idempotency checks key on the producer's event id.
    """
    from src.modules.platform.infrastructure.events.registry import DEAD_LETTER_STREAM
    from src.modules.platform.infrastructure.events.registry import EVENTS_STREAM
    from src.modules.platform.infrastructure.redis_client import get_async_redis_client

    client = get_async_redis_client()
    try:
        # The shared client decodes responses, so ids and fields are str.
        entries = cast(
            list[tuple[str, dict[str, str]]],
            await client.xrange(DEAD_LETTER_STREAM, count=args.limit),
        )
        for entry_id, fields in entries:
            original: dict[Any, Any] = {
                k: v for k, v in fields.items() if not k.startswith("dead_")
            }
            await client.xadd(EVENTS_STREAM, original)
            await client.xdel(DEAD_LETTER_STREAM, entry_id)
        print(f"Replayed {len(entries)} dead-lettered event(s).", flush=True)
        return 0
    finally:
        await client.aclose()


async def republish_outbox(args: argparse.Namespace) -> int:
    """Put relayed outbox events on the events stream once more.

    The recovery after Redis lost the events stream, by a restart without
    its data or a flush: every event the relay published from --since on
    (and before --until, when given) is appended to the stream again, and
    every consumer group sees it once more. Groups that already handled an
    event skip it, because they key on the producer's event id, so a
    --since earlier than needed costs little; docs/OPERATIONS.md section
    5.11 names the exceptions. The outbox keeps relayed events for 30 days. Times need a UTC offset, such as
    2026-11-04T06:00:00Z or 2026-11-04T07:00:00+01:00. --type, repeatable,
    limits it to some event types, and --dry-run only counts. Exits with 0
    when done, 1 when Redis failed part way (run it again with the same
    bounds), 2 for an unknown event type or an empty time range.
    """
    from collections import Counter

    import redis

    from src.bootstrap.cli.republish_outbox import republish
    from src.modules.platform.adapters.outbound.external.event_bus.redis_stream_event_bus import (
        RedisStreamEventBus,
    )
    from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
    from src.modules.platform.infrastructure.events.registry import EVENT_REGISTRY
    from src.modules.platform.infrastructure.redis_client import get_async_redis_client
    from src.modules.platform.ports.outbound.event_outbox_port import OutboxMessage

    event_types: list[str] = args.event_types or []
    unknown = sorted(set(event_types) - set(EVENT_REGISTRY))
    if unknown:
        print(f"Unknown event type(s): {', '.join(unknown)}.", file=sys.stderr, flush=True)
        return 2
    if args.until is not None and args.until <= args.since:
        print("--until must be later than --since.", file=sys.stderr, flush=True)
        return 2

    counts: Counter[str] = Counter()
    client = None if args.dry_run else get_async_redis_client()
    transport = RedisStreamEventBus(client) if client is not None else None

    async def publish(message: OutboxMessage) -> None:
        assert transport is not None  # never called on a dry run
        await transport.publish_raw(
            event_id=message.event_id,
            event_type=message.event_type,
            payload=message.payload,
        )

    try:
        try:
            await republish(
                session_factory=SessionLocal,
                publish=publish if transport is not None else None,
                since=args.since,
                until=args.until,
                event_types=event_types,
                counts=counts,
            )
        except redis.RedisError as error:
            print(
                f"Redis failed after {counts.total()} event(s): {error}. "
                "Run the command again with the same bounds.",
                file=sys.stderr,
                flush=True,
            )
            return 1
    finally:
        if client is not None:
            await client.aclose()

    for event_type, count in sorted(counts.items()):
        print(f"  {event_type}: {count}", flush=True)
    verb = "Would republish" if args.dry_run else "Republished"
    print(f"{verb} {counts.total()} event(s).", flush=True)
    return 0


def _aware_datetime(value: str) -> datetime:
    """An ISO 8601 time with a UTC offset; a time without one is refused
    rather than guessed."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"not an ISO 8601 time: {value!r}") from error
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError(
            f"{value!r} has no UTC offset; add one, such as Z or +01:00"
        )
    return parsed


async def pre_migration_dump(_: argparse.Namespace) -> int:
    """Dump the database when migrations are pending.

    The container entrypoint runs this before `alembic upgrade head` and
    refuses to migrate when it fails, unless GLADOS_SKIP_PRE_MIGRATION_DUMP
    is set. It dumps only when the database's revision differs from the
    heads of the image's migrations and the database holds tables, writes
    the dump to BACKUP__PRE_MIGRATION_DUMP_DIR (encrypted when
    SECURITY__BACKUP_ENCRYPTION_KEY is set) and keeps the newest
    BACKUP__PRE_MIGRATION_DUMP_KEEP dumps. `restore --file` reads them.
    Exits with 0 when a dump was written or none was needed, 1 when the
    dump failed. See docs/reference/operations-storage-and-backup.md
    section 5.
    """
    from src.bootstrap.cli.pre_migration_dump import run

    return await run()


async def lifecycle_drift(args: argparse.Namespace) -> int:
    """Report lifecycle fields that disagree with their derivation.

    Read-only. Compares the stored status of every lot, lot position,
    production order, order, order item and demand, the kind and completed
    count of every position, the stamps that record a status (a lot's
    completed_at, a production order's actual_end and an order's
    delivery_date) and an order's ordered_date with what
    the lifecycle rules derive from the recorded facts and intents, and
    prints each field that differs with the rule that decided it and the
    facts it read. A position whose facts give it more completed pieces than
    its quantity is listed as a fact anomaly, and so is an order line whose
    delivered, rejected or lost total differs from the sum over its delivery
    rows. Without --only, a part number a made or bought item carries without
    its registry entry, or under the other catalogue's entry, is listed as a
    fact anomaly too.

    Exits with 1 when any row differs, 0 otherwise, 2 for invalid arguments,
    and 3 with a one-line message on stderr when the run fails, for example
    because the database cannot be read. SQL echo is off for the run, so
    stdout carries only the report. See docs/reference/operations-lifecycle-repair.md section 1.
    """
    return await _derivation_drift(args)


async def _derivation_drift(args: argparse.Namespace) -> int:
    try:
        report = await _run_derivation_drift(args.only)
    except Exception as exc:
        # Every failure exits 3, so that 1 always means drift was found.
        print(f"lifecycle-drift failed: {_one_line(exc)}", file=sys.stderr, flush=True)
        return 3

    if args.json:
        print(json.dumps(_derivation_json(report), indent=2), flush=True)
    else:
        print("\n".join(_derivation_lines(report)), flush=True)
    return 1 if report.has_drift else 0


async def _run_derivation_drift(only: tuple[str, ...] | None) -> DriftReport:
    """Runs the report in a session of its own, on Postgres in one read-only
    snapshot. SQL echo is off for the run and restored afterwards."""
    from src.modules.catalogue.adapters.outbound.persistence.repositories.part_number_registry_repository import (
        SqlAlchemyPartNumberRegistryRepository,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
        sql_lifecycle_repositories,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
        start_read_only_snapshot,
    )
    from src.modules.fulfillment.application.services.lifecycle_drift import (
        LIFECYCLE_DRIFT_AGGREGATES,
    )
    from src.modules.fulfillment.application.services.lifecycle_drift import LifecycleDriftReport
    from src.modules.fulfillment.application.services.lifecycle_drift import (
        add_part_number_registry_anomalies,
    )
    from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
    from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
    from src.modules.platform.adapters.outbound.persistence.session import engine

    aggregates = (
        tuple(LifecycleAggregate(name) for name in only) if only else LIFECYCLE_DRIFT_AGGREGATES
    )
    echo = engine.echo
    engine.echo = False
    try:
        async with SessionLocal() as db:
            await start_read_only_snapshot(db)
            report = await LifecycleDriftReport(sql_lifecycle_repositories(db)).run(aggregates)
            if not only:
                await add_part_number_registry_anomalies(
                    report, SqlAlchemyPartNumberRegistryRepository(db)
                )
            return report
    finally:
        engine.echo = echo


async def lifecycle_repair(args: argparse.Namespace) -> int:
    """Write the lifecycle fields that disagree with their derivation.

    A dry run unless --apply is given: without it the command lists what it
    would write and changes nothing. It writes every stored status, kind,
    completed count and stamp that lifecycle-drift lists, through the
    lifecycle reconciler, with one changelog line per field ending in
    "(lifecycle repair)" in the system user's name. It publishes no events:
    no notification, mail, webhook or automatic print follows from a repair.
    Fact anomalies are listed for a manual step and left as they are.

    Each page of rows is repaired and committed in a transaction of its
    own, holding the row locks only for that page; a page that loses a race
    with a concurrent request is retried. Running it again changes nothing
    once everything is repaired.

    Exits with 0 when nothing is left to do, 1 when a dry run found rows or
    rows still differ after --apply (the fact anomalies among them), 2 for
    invalid arguments, and 3 with a one-line message on stderr when the run
    fails. Pages committed before a failure stay written. See
    docs/reference/operations-lifecycle-repair.md section 2.
    """
    try:
        report = await _run_lifecycle_repair(args.only, apply=args.apply, batch=args.batch)
    except Exception as exc:
        print(f"lifecycle-repair failed: {_one_line(exc)}", file=sys.stderr, flush=True)
        return 3

    if args.json:
        print(json.dumps(_repair_json(report), indent=2), flush=True)
    else:
        print("\n".join(_repair_lines(report)), flush=True)
    return 1 if report.needs_attention else 0


async def _run_lifecycle_repair(
    only: tuple[str, ...] | None, *, apply: bool, batch: int
) -> RepairReport:
    """Plans the repair in one read-only snapshot, or applies it as the
    system user, page by page. SQL echo is off for the run."""
    from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
        sql_lifecycle_repositories,
    )
    from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
        start_read_only_snapshot,
    )
    from src.modules.fulfillment.application.services.lifecycle_drift import (
        LIFECYCLE_DRIFT_AGGREGATES,
    )
    from src.modules.fulfillment.application.services.lifecycle_repair import LifecycleRepair
    from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
    from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
        SqlAlchemyUserRepository,
    )
    from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
    from src.modules.platform.adapters.outbound.persistence.session import engine
    from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
    from src.modules.platform.const import SYSTEM_USER

    aggregates = (
        tuple(LifecycleAggregate(name) for name in only) if only else LIFECYCLE_DRIFT_AGGREGATES
    )
    echo = engine.echo
    engine.echo = False
    try:
        async with SessionLocal() as db:
            repair = LifecycleRepair(
                sql_lifecycle_repositories(db),
                SqlAlchemyUnitOfWork(db),
                batch_size=batch,
                retryable=_lost_race,
            )
            if not apply:
                await start_read_only_snapshot(db)
                return await repair.plan(aggregates)
            actor = await SqlAlchemyUserRepository(db).get_by_username(SYSTEM_USER)
            if actor is None:
                raise LookupError(f"The system user {SYSTEM_USER!r} does not exist.")
            return await repair.apply(actor, aggregates)
    finally:
        engine.echo = echo


# deadlock_detected, serialization_failure, query_canceled (statement
# timeout) and lock_not_available (lock timeout): the page lost a race with a
# concurrent transaction and is worth repeating.
_LOST_RACE_SQLSTATES = frozenset({"40P01", "40001", "57014", "55P03"})


def _lost_race(exc: Exception) -> bool:
    """Whether a page failed by losing a race, which a retry can win: a
    database conflict or timeout, or a stale version check."""
    from sqlalchemy.orm.exc import StaleDataError

    if isinstance(exc, StaleDataError):
        return True
    orig = getattr(exc, "orig", None)
    return (getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)) in (
        _LOST_RACE_SQLSTATES
    )


def _drift_row_json(row: DriftRow) -> dict[str, object]:
    return {
        "table": row.table,
        "id": row.id,
        "public_id": str(row.public_id),
        "field": row.field,
        "stored": row.stored,
        "derived": row.derived,
        "rule": row.rule,
        "anomaly": row.anomaly,
        "facts": dict(row.facts),
    }


def _repair_json(report: RepairReport) -> dict[str, object]:
    """The repair as one JSON document."""
    from src.modules.fulfillment.application.services.lifecycle_repair import RepairAction

    return {
        "mode": "apply" if report.applied else "dry-run",
        "rows": [
            {
                "action": row.action.value,
                "table": row.table,
                "id": row.id,
                "public_id": str(row.public_id) if row.public_id is not None else None,
                "field": row.field,
                "stored": row.stored,
                "repaired": row.repaired,
                "rule": row.rule,
            }
            for row in report.rows
        ],
        "summary": {
            action.value: sum(1 for row in report.rows if row.action is action)
            for action in RepairAction
        },
        "left": [_drift_row_json(row) for row in report.left],
    }


def _aligned(rows: Sequence[tuple[str, ...]]) -> list[str]:
    """Pads every column but the last to its widest cell."""
    widths = [max(len(cells[column]) for cells in rows) for column in range(len(rows[0]) - 1)]
    return [
        "  ".join(
            [*(cell.ljust(width) for cell, width in zip(cells, widths, strict=False)), cells[-1]]
        )
        for cells in rows
    ]


def _repair_lines(report: RepairReport) -> list[str]:
    """The repair as an aligned table followed by its summary."""
    from src.modules.fulfillment.application.services.lifecycle_repair import RepairAction

    if report.applied:
        intro = (
            "Lifecycle repair. The rows below were written as the system user, without "
            "events; rows that still differ from their derivation follow them."
        )
    else:
        intro = (
            "Lifecycle repair, dry run. Nothing was written; run it with --apply to write "
            "the rows below. Manual rows are fact anomalies the repair leaves alone."
        )
    lines = [intro, ""]
    if report.rows:
        header = ("action", "table", "id", "public_id", "field", "stored", "repaired", "rule")
        lines += _aligned(
            [header]
            + [
                (
                    row.action.value,
                    row.table,
                    str(row.id),
                    str(row.public_id) if row.public_id is not None else "-",
                    row.field,
                    row.stored,
                    row.repaired,
                    row.rule,
                )
                for row in report.rows
            ]
        )
        lines.append("")
    if report.left:
        lines.append("Still differing:")
        left_header = ("table", "id", "public_id", "field", "stored", "derived", "rule")
        lines += _aligned(
            [left_header]
            + [
                (
                    row.table,
                    str(row.id),
                    str(row.public_id),
                    row.field,
                    row.stored,
                    row.derived,
                    row.rule,
                )
                for row in report.left
            ]
        )
        lines.append("")
    counts = ", ".join(
        f"{sum(1 for row in report.rows if row.action is action)} {action.value}"
        for action in RepairAction
    )
    lines.append(f"{'Written' if report.applied else 'Planned'}: {counts}.")
    if report.applied:
        lines.append(
            f"{len(report.left)} row(s) still differ." if report.left else "No drift left."
        )
    elif not report.rows:
        lines.append("Nothing to repair.")
    return lines


def _one_line(exc: Exception) -> str:
    """The exception's type and the first line of its message."""
    lines = str(exc).strip().splitlines()
    return f"{type(exc).__name__}: {lines[0]}" if lines else type(exc).__name__


def _drift_facts(facts: Mapping[str, object]) -> str:
    return " ".join(f"{key}={_drift_value(value)}" for key, value in facts.items())


def _drift_value(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, list | tuple):
        return ",".join(_drift_value(item) for item in value) or "-"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _derivation_json(report: DriftReport) -> dict[str, object]:
    """The report as one JSON document."""
    return {
        "mode": "authoritative",
        "drift": len(report.rows),
        "rows": [_drift_row_json(row) for row in report.rows],
        "summary": {
            table: {"checked": tally.checked, "drift": tally.drift}
            for table, tally in report.tallies.items()
        },
    }


def _derivation_lines(report: DriftReport) -> list[str]:
    """The report as an aligned table followed by one summary line per
    aggregate."""
    lines = [
        "Lifecycle drift report. Stored lifecycle fields are compared with their "
        "derivation from the recorded facts and intents; a fact anomaly is marked "
        "in the rule column.",
        "",
    ]
    if report.rows:
        header = ("table", "id", "public_id", "field", "stored", "derived", "rule", "facts")
        table = [header] + [
            (
                row.table,
                str(row.id),
                str(row.public_id),
                row.field,
                row.stored,
                row.derived,
                row.rule,
                _drift_facts(row.facts),
            )
            for row in report.rows
        ]
        widths = [max(len(cells[column]) for cells in table) for column in range(7)]
        for cells in table:
            padded = [cell.ljust(width) for cell, width in zip(cells[:7], widths, strict=True)]
            lines.append("  ".join([*padded, cells[7]]))
        lines.append("")
    lines.extend(
        f"{name}: {tally.checked} checked, {tally.drift} differ."
        for name, tally in report.tallies.items()
    )
    lines.append(f"{len(report.rows)} row(s) differ." if report.rows else "No drift found.")
    return lines


def _drift_aggregates(value: str) -> tuple[str, ...]:
    """Parses --only, a comma-separated subset of the report's tables."""
    from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate

    known = [a.value for a in LifecycleAggregate]
    names = tuple(dict.fromkeys(name.strip() for name in value.split(",") if name.strip()))
    if not names or any(name not in known for name in names):
        raise argparse.ArgumentTypeError(f"expected a comma-separated subset of {', '.join(known)}")
    return names


_COMMANDS: dict[str, Callable[[argparse.Namespace], Coroutine[Any, Any, int]]] = {
    "enable-local-login": enable_local_login,
    "disable-ldap": disable_ldap,
    "reset-totp": reset_totp,
    "unlock-users": unlock_users,
    "replay-dead-letters": replay_dead_letters,
    "republish-outbox": republish_outbox,
    "pre-migration-dump": pre_migration_dump,
    "lifecycle-drift": lifecycle_drift,
    "lifecycle-repair": lifecycle_repair,
}


def _add_lifecycle_drift_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate

    drift = subparsers.add_parser(
        "lifecycle-drift",
        help="Report lifecycle fields that disagree with their derivation (read-only).",
        description=lifecycle_drift.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    drift.add_argument(
        "--json", action="store_true", help="Print one JSON document instead of the table."
    )
    drift.add_argument(
        "--only",
        type=_drift_aggregates,
        default=None,
        metavar="TABLES",
        help=(
            f"Comma-separated subset of {', '.join(a.value for a in LifecycleAggregate)} "
            f"(default: all)."
        ),
    )


# Rows per page of the repair, each page one transaction.
_REPAIR_BATCH_SIZE = 200


def _batch_size(value: str) -> int:
    """Parses --batch, a positive number of rows per page."""
    try:
        size = int(value)
    except ValueError:
        size = 0
    if size < 1:
        raise argparse.ArgumentTypeError("expected a positive whole number")
    return size


def _add_lifecycle_repair_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate

    repair = subparsers.add_parser(
        "lifecycle-repair",
        help=(
            "Write the lifecycle fields that disagree with their derivation "
            "(dry run unless --apply; publishes no events)."
        ),
        description=lifecycle_repair.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    repair.add_argument(
        "--apply", action="store_true", help="Write the repair (default: only list it)."
    )
    repair.add_argument(
        "--json", action="store_true", help="Print one JSON document instead of the table."
    )
    repair.add_argument(
        "--only",
        type=_drift_aggregates,
        default=None,
        metavar="TABLES",
        help=(
            f"Comma-separated subset of {', '.join(a.value for a in LifecycleAggregate)} "
            f"to start from (default: all)."
        ),
    )
    repair.add_argument(
        "--batch",
        type=_batch_size,
        default=_REPAIR_BATCH_SIZE,
        metavar="N",
        help=f"Rows per page and transaction (default: {_REPAIR_BATCH_SIZE}).",
    )


def main() -> None:
    from src.bootstrap.registrations import register_all

    register_all()
    parser = argparse.ArgumentParser(
        prog="admin",
        description="Glados recovery and diagnostic commands.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  docker compose run --rm backend admin enable-local-login\n"
            "  docker compose run --rm backend admin reset-totp alice\n"
            "  docker compose run --rm backend admin unlock-users\n"
            "  docker compose run --rm backend admin republish-outbox --since 2026-11-04T06:00Z\n"
            "  docker compose run --rm backend admin lifecycle-drift\n"
            "  docker compose run --rm backend admin lifecycle-repair --apply\n"
            "\n"
            "Without a host shell (e.g. Portainer console into `backend` or the\n"
            "`maintenance` profile, see docs/OPERATIONS.md section 6):\n"
            "  python -m src.bootstrap.cli.admin enable-local-login"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    subparsers.add_parser(
        "enable-local-login",
        help="Re-enable password login after it was switched off.",
        description=enable_local_login.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers.add_parser(
        "disable-ldap",
        help="Turn directory (LDAP) authentication back off.",
        description=disable_ldap.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    reset = subparsers.add_parser(
        "reset-totp",
        help="Clear a user's 2FA enrolment.",
        description=reset_totp.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    reset.add_argument("username", metavar="USERNAME", help="The user whose 2FA to clear.")

    unlock = subparsers.add_parser(
        "unlock-users",
        help="Release failed-login lockouts.",
        description=unlock_users.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    unlock.add_argument(
        "--user",
        dest="username",
        default=None,
        metavar="USERNAME",
        help="Release only this user (default: everyone).",
    )

    replay = subparsers.add_parser(
        "replay-dead-letters",
        help="Put dead-lettered events back on the events stream.",
        description=replay_dead_letters.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    replay.add_argument(
        "--limit",
        type=int,
        default=100,
        metavar="N",
        help="Replay at most this many, oldest first (default: 100).",
    )

    republish_parser = subparsers.add_parser(
        "republish-outbox",
        help="Put relayed outbox events on the events stream once more.",
        description=republish_outbox.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    republish_parser.add_argument(
        "--since",
        required=True,
        type=_aware_datetime,
        metavar="TIME",
        help="Republish events the relay published at or after this time.",
    )
    republish_parser.add_argument(
        "--until",
        type=_aware_datetime,
        default=None,
        metavar="TIME",
        help="Only events published before this time (default: up to now).",
    )
    republish_parser.add_argument(
        "--type",
        dest="event_types",
        action="append",
        default=None,
        metavar="EVENT_TYPE",
        help="Only this event type, such as OrderCanceled; repeat for more.",
    )
    republish_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only count the events per type, publish nothing.",
    )

    subparsers.add_parser(
        "pre-migration-dump",
        help="Dump the database when migrations are pending (the entrypoint runs this).",
        description=pre_migration_dump.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    _add_lifecycle_drift_parser(subparsers)
    _add_lifecycle_repair_parser(subparsers)

    args = parser.parse_args()
    sys.exit(asyncio.run(_COMMANDS[args.command](args)))


if __name__ == "__main__":
    main()
