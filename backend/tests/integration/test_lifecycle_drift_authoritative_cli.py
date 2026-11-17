"""
`admin lifecycle-drift`, end to end on the throwaway SQLite
database: seeded drift is reported as JSON or as a table with exit code 1 and
changes nothing, a line whose delivery totals differ from its delivery rows
is reported as an anomaly, a consistent database exits 0, --only limits the
tables, a database that cannot be read exits 3, and the command runs as its
own process.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import src.modules.platform.adapters.outbound.persistence.session as session_module
from src.bootstrap.cli import admin
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
    sql_lifecycle_repositories,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.application.services.lifecycle_drift import LifecycleDriftReport
from tests.integration import _lifecycle_seed as seed

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _args(*, json_output: bool, only: tuple[str, ...] | None = None) -> argparse.Namespace:
    return argparse.Namespace(json=json_output, only=only)


async def _seed_drift(db: AsyncSession) -> dict[str, int]:
    """A lot whose line arrived in full while every stored status still says
    ordered, and a bought line canceled by its intent but stored as ordered."""
    lot = await seed.lot(db, "planned")
    position = await seed.position(db, lot, "external", "ordered_or_queued")
    order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    made_line = await seed.line(
        db, order, "ordered", at=position, ordered_date=seed.NOW, quantity_delivered=10.0
    )
    canceled = await seed.line(db, order, "ordered", ordered_date=seed.NOW, canceled_at=seed.NOW)
    await db.commit()
    return {
        "lot": lot.id,
        "position": position.id,
        "order": order.id,
        "made_line": made_line.id,
        "canceled": canceled.id,
    }


async def _made_item(db: AsyncSession, part_number: str) -> int:
    """A made item carrying `part_number` with no registry entry."""
    item = await seed.add(
        db,
        MadeItemOrmModel(
            created=seed.NOW,
            changed=seed.NOW,
            changes=[],
            revision="A",
            article_name="Bracket",
            status="active",
            data_source="WEB",
            part_number=part_number,
            creator_id=1,
        ),
    )
    await db.commit()
    return item.id


async def _seed_consistent(db: AsyncSession) -> None:
    lot = await seed.lot(db, "planned")
    position = await seed.position(db, lot, "external", "ordered_or_queued")
    order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    await seed.line(db, order, "ordered", at=position, ordered_date=seed.NOW)
    await seed.bought_demand(
        db, "ordered", await seed.line(db, order, "ordered", ordered_date=seed.NOW), 10.0
    )
    await db.commit()


async def test_seeded_drift_is_reported_as_json_and_nothing_changes(
    db: AsyncSession, capsys: pytest.CaptureFixture[str], allow_lifecycle_drift: None
) -> None:
    ids = await _seed_drift(db)

    code = await admin.lifecycle_drift(_args(json_output=True))

    assert code == 1
    document = json.loads(capsys.readouterr().out)
    assert document["mode"] == "authoritative"
    found = {(row["table"], row["id"], row["field"]) for row in document["rows"]}
    assert found == {
        ("order_items", ids["made_line"], "status"),
        ("order_items", ids["canceled"], "status"),
        ("orders", ids["order"], "status"),
        ("orders", ids["order"], "delivery_date"),
        ("lot_positions", ids["position"], "status"),
        ("lot_positions", ids["position"], "quantity_completed"),
        ("lots", ids["lot"], "status"),
        ("lots", ids["lot"], "completed_at"),
    }
    lot_row = next(row for row in document["rows"] if row["table"] == "lots")
    assert lot_row["rule"].startswith("lot_status row 3: ")
    assert lot_row["facts"]["position_statuses"] == ["completed"]
    assert document["summary"]["lots"] == {"checked": 1, "drift": 2}
    async with session_module.SessionLocal() as fresh:
        assert (await fresh.get_one(ProductionLotOrmModel, ids["lot"])).status == "planned"
        assert (await fresh.get_one(OrderItemOrmModel, ids["canceled"])).status == "ordered"


async def test_delivered_pieces_without_their_row_are_reported_as_an_anomaly(
    db: AsyncSession, capsys: pytest.CaptureFixture[str], allow_lifecycle_drift: None
) -> None:
    order = await seed.order(db, "delivered", ordered_date=seed.NOW, delivery_date=seed.NOW)
    line = await seed.line(
        db, order, "delivered", ordered_date=seed.NOW, quantity_delivered=10.0, booked=False
    )
    await db.commit()

    code = await admin.lifecycle_drift(_args(json_output=True))

    assert code == 1
    [row] = json.loads(capsys.readouterr().out)["rows"]
    assert (row["table"], row["id"], row["field"], row["anomaly"]) == (
        "order_items",
        line.id,
        "quantity_delivered",
        True,
    )
    assert (row["stored"], row["derived"]) == ("10", "0")


async def test_a_part_number_without_its_registry_entry_is_reported_as_an_anomaly(
    db: AsyncSession, capsys: pytest.CaptureFixture[str], allow_lifecycle_drift: None
) -> None:
    item_id = await _made_item(db, "PN-LOST")

    code = await admin.lifecycle_drift(_args(json_output=True))

    assert code == 1
    document = json.loads(capsys.readouterr().out)
    [row] = [r for r in document["rows"] if r["table"] == "part_number_registry"]
    assert (row["id"], row["field"], row["stored"], row["derived"], row["anomaly"]) == (
        item_id,
        "part_number",
        "-",
        "made",
        True,
    )
    assert row["facts"]["part_number"] == "PN-LOST"
    assert document["summary"]["part_number_registry"]["drift"] == 1


async def test_only_leaves_the_part_number_registry_out(
    db: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    await _made_item(db, "PN-LOST")

    code = await admin.lifecycle_drift(_args(json_output=True, only=("orders",)))

    assert code == 0
    assert "part_number_registry" not in json.loads(capsys.readouterr().out)["summary"]


async def test_a_consistent_database_exits_zero_with_a_summary(
    db: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    await _seed_consistent(db)

    code = await admin.lifecycle_drift(_args(json_output=False))

    assert code == 0
    lines = capsys.readouterr().out.splitlines()
    assert "lots: 1 checked, 0 differ." in lines
    assert "order_items: 2 checked, 0 differ." in lines
    assert "bought_demands: 1 checked, 0 differ." in lines
    assert lines[-1] == "No drift found."


async def test_only_limits_the_report_to_the_chosen_tables(
    db: AsyncSession, capsys: pytest.CaptureFixture[str], allow_lifecycle_drift: None
) -> None:
    ids = await _seed_drift(db)

    code = await admin.lifecycle_drift(_args(json_output=False, only=("orders",)))

    assert code == 1
    lines = capsys.readouterr().out.splitlines()
    cells = [line.split() for line in lines if line.startswith("orders ")]
    assert {(row[1], row[3]) for row in cells} == {
        (str(ids["order"]), "status"),
        (str(ids["order"]), "delivery_date"),
    }
    assert not any(line.startswith(("lots", "order_items")) for line in lines)


async def test_the_report_pages_through_every_row(
    db: AsyncSession, allow_lifecycle_drift: None
) -> None:
    for _ in range(3):
        await seed.order(db, "ordered")
    await db.commit()

    report = await LifecycleDriftReport(sql_lifecycle_repositories(db), batch_size=1).run()

    assert report.tallies["orders"].checked == 3
    assert [row.field for row in report.rows if row.table == "orders"] == ["status"] * 3


async def test_a_database_that_cannot_be_read_exits_three(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    unreadable = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'missing' / 'drift.db'}", poolclass=NullPool
    )
    monkeypatch.setattr(session_module, "SessionLocal", async_sessionmaker(bind=unreadable))
    try:
        code = await admin.lifecycle_drift(_args(json_output=True))
    finally:
        await unreadable.dispose()

    assert code == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    [message] = captured.err.splitlines()
    assert message.startswith("lifecycle-drift failed: OperationalError: ")


async def test_the_command_runs_as_its_own_process(
    db: AsyncSession, allow_lifecycle_drift: None
) -> None:
    # This suite loads every model up front; the command's own process loads
    # only what it imports, so a model it misses fails here alone.
    ids = await _seed_drift(db)
    env = {key: value for key, value in os.environ.items() if key != "ENV_FILE"}
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "src.bootstrap.cli.admin",
        "lifecycle-drift",
        "--json",
        cwd=_BACKEND_ROOT,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)

    assert process.returncode == 1, stderr.decode()
    rows = json.loads(stdout)["rows"]
    assert ("lots", ids["lot"], "status") in {(r["table"], r["id"], r["field"]) for r in rows}
