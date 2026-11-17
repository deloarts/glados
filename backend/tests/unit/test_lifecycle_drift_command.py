"""
`admin lifecycle-drift` runs the report against the lifecycle derivation:
its JSON and text output, the exit codes (1 on drift, 0 without, 2 for
invalid arguments, 3 when the run fails) and the --only vocabulary. The
report itself is stubbed here; it is covered on the fake world and on the
test database.
"""

import argparse
import json
import sys
from typing import Any
from uuid import UUID

import pytest

from src.bootstrap.cli import admin
from src.modules.fulfillment.application.services.lifecycle_drift import DriftReport
from src.modules.fulfillment.application.services.lifecycle_drift import DriftRow
from src.modules.fulfillment.application.services.lifecycle_drift import DriftTally

_PUBLIC_ID = UUID("00000000-0000-0000-0000-000000000042")


def _report(*rows: DriftRow) -> DriftReport:
    return DriftReport(
        rows=list(rows),
        tallies={"lots": DriftTally(checked=2, drift=len(rows)), "orders": DriftTally(checked=1)},
    )


def _row(**values: object) -> DriftRow:
    defaults: dict[str, object] = {
        "table": "lots",
        "id": 42,
        "public_id": _PUBLIC_ID,
        "field": "status",
        "stored": "planned",
        "derived": "completed",
        "rule": "lot_status row 3: every position COMPLETED",
        "facts": {"quantity": 10.0, "position_statuses": ["completed"]},
    }
    return DriftRow(**{**defaults, **values})  # type: ignore[arg-type]


def _args(**values: object) -> argparse.Namespace:
    return argparse.Namespace(**{"json": False, "only": None, **values})


def _stub_report(monkeypatch: pytest.MonkeyPatch, report: DriftReport) -> list[object]:
    calls: list[object] = []

    async def run(only: tuple[str, ...] | None) -> DriftReport:
        calls.append(only)
        return report

    monkeypatch.setattr(admin, "_run_derivation_drift", run)
    return calls


async def test_the_command_reports_the_derivation_as_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = _stub_report(monkeypatch, _report(_row(anomaly=False)))

    code = await admin.lifecycle_drift(_args(json=True, only=("lots",)))

    assert code == 1
    assert calls == [("lots",)]
    document = json.loads(capsys.readouterr().out)
    assert document["mode"] == "authoritative"
    assert document["drift"] == 1
    assert document["rows"] == [
        {
            "table": "lots",
            "id": 42,
            "public_id": str(_PUBLIC_ID),
            "field": "status",
            "stored": "planned",
            "derived": "completed",
            "rule": "lot_status row 3: every position COMPLETED",
            "anomaly": False,
            "facts": {"quantity": 10.0, "position_statuses": ["completed"]},
        }
    ]
    assert document["summary"] == {
        "lots": {"checked": 2, "drift": 1},
        "orders": {"checked": 1, "drift": 0},
    }


async def test_the_text_report_shows_the_field_column_and_a_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_report(monkeypatch, _report(_row()))

    code = await admin.lifecycle_drift(_args())

    assert code == 1
    lines = capsys.readouterr().out.splitlines()
    header = next(line for line in lines if line.startswith("table"))
    assert header.split() == [
        "table",
        "id",
        "public_id",
        "field",
        "stored",
        "derived",
        "rule",
        "facts",
    ]
    row = lines[lines.index(header) + 1]
    assert row.split()[:6] == ["lots", "42", str(_PUBLIC_ID), "status", "planned", "completed"]
    assert row.endswith("quantity=10 position_statuses=completed")
    assert "lots: 2 checked, 1 differ." in lines
    assert lines[-1] == "1 row(s) differ."


async def test_a_clean_report_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_report(monkeypatch, _report())

    assert await admin.lifecycle_drift(_args()) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "No drift found."


async def test_a_failing_run_exits_three_with_one_line_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def run(only: tuple[str, ...] | None) -> DriftReport:
        raise RuntimeError("database is gone\nmore detail")

    monkeypatch.setattr(admin, "_run_derivation_drift", run)

    code = await admin.lifecycle_drift(_args(json=True))

    captured = capsys.readouterr()
    assert code == 3
    assert captured.out == ""
    assert captured.err.strip() == "lifecycle-drift failed: RuntimeError: database is gone"


def test_only_takes_every_lifecycle_table() -> None:
    assert admin._drift_aggregates("production_orders,order_items, lots") == (
        "production_orders",
        "order_items",
        "lots",
    )


def test_only_rejects_an_unknown_table(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["admin", "lifecycle-drift", "--only", "lots,lotz"])

    with pytest.raises(SystemExit) as exited:
        admin.main()

    assert exited.value.code == 2
    assert "--only" in capsys.readouterr().err


class _Dialect:
    def __init__(self, name: str) -> None:
        self.name = name


class _RecordingSession:
    """A session that records the statements it executes; the report run and
    the part number registry check are stubbed, so nothing else reaches it."""

    def __init__(self, dialect: str, log: list[str]) -> None:
        self._dialect = _Dialect(dialect)
        self._log = log

    async def __aenter__(self) -> "_RecordingSession":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    def get_bind(self) -> object:
        return argparse.Namespace(dialect=self._dialect)

    async def execute(self, statement: object) -> None:
        self._log.append(str(statement))


@pytest.mark.parametrize(
    ("dialect", "expected"),
    [
        (
            "postgresql",
            ["SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY", "report", "registry"],
        ),
        ("sqlite", ["report", "registry"]),
    ],
)
async def test_the_report_runs_in_a_read_only_snapshot_on_postgres(
    monkeypatch: pytest.MonkeyPatch, dialect: str, expected: list[str]
) -> None:
    import src.modules.platform.adapters.outbound.persistence.session as session_module
    from src.modules.fulfillment.application.services import lifecycle_drift

    log: list[str] = []
    opened: list[_RecordingSession] = []
    registry_sessions: list[object] = []

    def open_session() -> _RecordingSession:
        opened.append(_RecordingSession(dialect, log))
        return opened[-1]

    async def run(self: object, aggregates: object, *, now: object = None) -> DriftReport:
        log.append("report")
        return DriftReport()

    async def add_registry_anomalies(report: DriftReport, registry: Any) -> None:
        log.append("registry")
        registry_sessions.append(registry._db)

    monkeypatch.setattr(session_module, "SessionLocal", open_session)
    monkeypatch.setattr(lifecycle_drift.LifecycleDriftReport, "run", run)
    monkeypatch.setattr(
        lifecycle_drift, "add_part_number_registry_anomalies", add_registry_anomalies
    )

    report = await admin._run_derivation_drift(None)

    # The registry check reads in the snapshot of the report, after it in
    # the same session, so both see one state of the database.
    assert log == expected
    assert len(opened) == 1
    assert registry_sessions == opened
    assert not report.has_drift
