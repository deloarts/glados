"""
`admin lifecycle-repair`: a dry run unless --apply, its JSON and text
output, the exit codes (1 when a dry run finds rows or rows still differ
after --apply, 0 otherwise, 2 for invalid arguments, 3 when the run fails),
the --batch and --only vocabulary, which failures count as a lost race, and
that a dry run reads in a read-only snapshot. The repair itself is stubbed
here; it is covered on the fake world and on the test database.
"""

import argparse
import json
import sys
from uuid import UUID

import pytest

from src.bootstrap.cli import admin
from src.modules.fulfillment.application.services.lifecycle_drift import DriftRow
from src.modules.fulfillment.application.services.lifecycle_repair import RepairAction
from src.modules.fulfillment.application.services.lifecycle_repair import RepairReport
from src.modules.fulfillment.application.services.lifecycle_repair import RepairRow

_PUBLIC_ID = UUID("00000000-0000-0000-0000-000000000042")


def _row(action: RepairAction = RepairAction.DERIVED, **values: object) -> RepairRow:
    defaults: dict[str, object] = {
        "action": action,
        "table": "lots",
        "id": 42,
        "public_id": _PUBLIC_ID,
        "field": "status",
        "stored": "planned",
        "repaired": "completed",
        "rule": "lot_status row 3: every position COMPLETED",
    }
    return RepairRow(**{**defaults, **values})  # type: ignore[arg-type]


def _left() -> DriftRow:
    return DriftRow(
        table="order_items",
        id=7,
        public_id=_PUBLIC_ID,
        field="quantity_delivered",
        stored="10",
        derived="0",
        rule="fact anomaly",
        facts={},
        anomaly=True,
    )


def _args(**values: object) -> argparse.Namespace:
    return argparse.Namespace(
        **{"json": False, "only": None, "apply": False, "batch": 200, **values}
    )


def _stub(monkeypatch: pytest.MonkeyPatch, report: RepairReport) -> list[object]:
    calls: list[object] = []

    async def run(only: tuple[str, ...] | None, *, apply: bool, batch: int) -> RepairReport:
        calls.append((only, apply, batch))
        return report

    monkeypatch.setattr(admin, "_run_lifecycle_repair", run)
    return calls


async def test_a_dry_run_lists_the_plan_as_json_and_exits_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = _stub(monkeypatch, RepairReport(applied=False, rows=[_row()]))

    code = await admin.lifecycle_repair(_args(json=True, only=("lots",), batch=50))

    assert code == 1
    assert calls == [(("lots",), False, 50)]
    document = json.loads(capsys.readouterr().out)
    assert document["mode"] == "dry-run"
    assert document["rows"] == [
        {
            "action": "derived",
            "table": "lots",
            "id": 42,
            "public_id": str(_PUBLIC_ID),
            "field": "status",
            "stored": "planned",
            "repaired": "completed",
            "rule": "lot_status row 3: every position COMPLETED",
        }
    ]
    assert document["summary"] == {"derived": 1, "manual": 0}
    assert document["left"] == []


async def test_the_text_output_shows_the_rows_and_a_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub(
        monkeypatch,
        RepairReport(
            applied=False,
            rows=[
                _row(),
                _row(
                    RepairAction.MANUAL,
                    table="lot_positions",
                    field="quantity_completed",
                    stored="10",
                    repaired="12",
                    rule="fact anomaly",
                ),
            ],
        ),
    )

    code = await admin.lifecycle_repair(_args())

    assert code == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("Lifecycle repair, dry run. Nothing was written")
    header = next(line for line in lines if line.startswith("action"))
    assert header.split() == [
        "action",
        "table",
        "id",
        "public_id",
        "field",
        "stored",
        "repaired",
        "rule",
    ]
    assert lines[-1] == "Planned: 1 derived, 1 manual."


async def test_an_apply_that_leaves_nothing_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = _stub(monkeypatch, RepairReport(applied=True, rows=[_row()]))

    code = await admin.lifecycle_repair(_args(apply=True))

    assert code == 0
    assert calls == [(None, True, 200)]
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("Lifecycle repair. The rows below were written as the system user")
    assert lines[-2:] == [
        "Written: 1 derived, 0 manual.",
        "No drift left.",
    ]


async def test_an_apply_that_leaves_rows_exits_one_and_lists_them(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub(monkeypatch, RepairReport(applied=True, left=[_left()]))

    code = await admin.lifecycle_repair(_args(apply=True, json=True))

    assert code == 1
    document = json.loads(capsys.readouterr().out)
    assert document["mode"] == "apply"
    assert [row["field"] for row in document["left"]] == ["quantity_delivered"]
    assert document["left"][0]["anomaly"] is True


async def test_a_dry_run_without_rows_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub(monkeypatch, RepairReport(applied=False))

    assert await admin.lifecycle_repair(_args()) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "Nothing to repair."


async def test_a_failing_run_exits_three_with_one_line_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def run(only: tuple[str, ...] | None, *, apply: bool, batch: int) -> RepairReport:
        raise LookupError("The system user 'system' does not exist.\nmore")

    monkeypatch.setattr(admin, "_run_lifecycle_repair", run)

    code = await admin.lifecycle_repair(_args(apply=True))

    captured = capsys.readouterr()
    assert code == 3
    assert captured.out == ""
    assert captured.err.strip() == (
        "lifecycle-repair failed: LookupError: The system user 'system' does not exist."
    )


@pytest.mark.parametrize("argv", [["--batch", "0"], ["--batch", "many"], ["--only", "lotz"]])
def test_invalid_arguments_exit_two(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], argv: list[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["admin", "lifecycle-repair", *argv])

    with pytest.raises(SystemExit) as exited:
        admin.main()

    assert exited.value.code == 2
    assert argv[0] in capsys.readouterr().err


def test_the_command_is_a_dry_run_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[argparse.Namespace] = []

    async def command(args: argparse.Namespace) -> int:
        seen.append(args)
        return 0

    monkeypatch.setitem(admin._COMMANDS, "lifecycle-repair", command)
    monkeypatch.setattr(sys, "argv", ["admin", "lifecycle-repair"])

    with pytest.raises(SystemExit) as exited:
        admin.main()

    assert exited.value.code == 0
    [args] = seen
    assert (args.apply, args.json, args.only, args.batch) == (False, False, None, 200)


class _Orig:
    def __init__(self, sqlstate: str) -> None:
        self.sqlstate = sqlstate


class _DatabaseError(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__(sqlstate)
        self.orig = _Orig(sqlstate)


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (_DatabaseError("40P01"), True),
        (_DatabaseError("55P03"), True),
        (_DatabaseError("57014"), True),
        (_DatabaseError("40001"), True),
        (_DatabaseError("23505"), False),
        (RuntimeError("broken"), False),
    ],
)
def test_only_a_conflict_a_timeout_or_a_stale_version_is_a_lost_race(
    exc: Exception, expected: bool
) -> None:
    assert admin._lost_race(exc) is expected


def test_a_stale_version_is_a_lost_race() -> None:
    from sqlalchemy.orm.exc import StaleDataError

    assert admin._lost_race(StaleDataError("version")) is True


class _Dialect:
    def __init__(self, name: str) -> None:
        self.name = name


class _RecordingSession:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def __aenter__(self) -> "_RecordingSession":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    def get_bind(self) -> object:
        return argparse.Namespace(dialect=_Dialect("postgresql"))

    async def execute(self, statement: object) -> None:
        self._log.append(str(statement))


async def test_a_dry_run_reads_in_a_read_only_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.modules.platform.adapters.outbound.persistence.session as session_module
    from src.modules.fulfillment.application.services import lifecycle_repair

    log: list[str] = []

    async def plan(self: object, aggregates: object) -> RepairReport:
        log.append("plan")
        return RepairReport(applied=False)

    monkeypatch.setattr(session_module, "SessionLocal", lambda: _RecordingSession(log))
    monkeypatch.setattr(lifecycle_repair.LifecycleRepair, "plan", plan)

    report = await admin._run_lifecycle_repair(None, apply=False, batch=200)

    assert log == ["SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY", "plan"]
    assert not report.needs_attention
