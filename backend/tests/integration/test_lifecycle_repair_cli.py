"""
`admin lifecycle-repair`, end to end on the throwaway SQLite database. A dry
run lists the seeded drift and changes nothing. --apply writes it as the
system user with a "lifecycle repair" changelog line and dates a missing
stamp at the run, after which the drift report is clean and a second run
finds nothing. Delivered pieces without their row are
left for a manual step, a missing system user exits 3, and the command runs
as its own process.
"""

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import src.modules.platform.adapters.outbound.persistence.session as session_module
from src.bootstrap.cli import admin
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.platform.const import SYSTEM_USER
from src.modules.platform.domain.entities.user import User
from tests.integration import _lifecycle_seed as seed

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
EARLIER = seed.NOW - timedelta(days=3)


def _args(*, apply: bool, json_output: bool = True) -> argparse.Namespace:
    return argparse.Namespace(json=json_output, only=None, apply=apply, batch=200)


async def _system_user(create_user: Callable[..., Awaitable[User]]) -> User:
    return await create_user(username=SYSTEM_USER, email="system@example.com", is_systemuser=True)


async def _seed(db: AsyncSession) -> dict[str, int]:
    """A lot whose external line arrived in full while the stored statuses
    still say ordered, and an order stored delivered without its date."""
    lot = await seed.lot(db, "planned")
    position = await seed.position(db, lot, "external", "ordered_or_queued")
    placed = await seed.order(db, "ordered", ordered_date=seed.NOW)
    await seed.line(
        db, placed, "ordered", at=position, ordered_date=seed.NOW, quantity_delivered=10.0
    )
    delivered = await seed.order(db, "delivered", ordered_date=seed.NOW, changed=EARLIER)
    await seed.line(db, delivered, "delivered", ordered_date=seed.NOW, quantity_delivered=10.0)
    await db.commit()
    return {
        "lot": lot.id,
        "delivered": delivered.id,
    }


async def test_a_dry_run_lists_the_repair_and_changes_nothing(
    db: AsyncSession, capsys: pytest.CaptureFixture[str], allow_lifecycle_drift: None
) -> None:
    ids = await _seed(db)

    code = await admin.lifecycle_repair(_args(apply=False))

    assert code == 1
    document = json.loads(capsys.readouterr().out)
    assert document["mode"] == "dry-run"
    found = {(r["action"], r["table"], r["id"], r["field"]) for r in document["rows"]}
    assert {
        ("derived", "lots", ids["lot"], "status"),
        ("derived", "orders", ids["delivered"], "delivery_date"),
    } <= found
    async with session_module.SessionLocal() as fresh:
        assert (await fresh.get_one(ProductionLotOrmModel, ids["lot"])).status == "planned"


async def test_apply_repairs_as_the_system_user_and_leaves_no_drift(
    db: AsyncSession,
    capsys: pytest.CaptureFixture[str],
    create_user: Callable[..., Awaitable[User]],
) -> None:
    system = await _system_user(create_user)
    ids = await _seed(db)

    code = await admin.lifecycle_repair(_args(apply=True))

    assert code == 0, capsys.readouterr().out
    document = json.loads(capsys.readouterr().out)
    assert document["mode"] == "apply" and document["left"] == []
    async with session_module.SessionLocal() as fresh:
        lot = await fresh.get_one(ProductionLotOrmModel, ids["lot"])
        assert lot.status == "completed"
        assert lot.changes[0].endswith("Status: planned → completed (lifecycle repair).")
        assert system.full_name in lot.changes[0]
        delivered = await fresh.get_one(OrderOrmModel, ids["delivered"])
        assert delivered.delivery_date is not None
        assert delivered.changes[-1].endswith("Delivery date: set (lifecycle repair).")

    assert await admin.lifecycle_drift(argparse.Namespace(json=True, only=None)) == 0
    capsys.readouterr()
    assert await admin.lifecycle_repair(_args(apply=True)) == 0
    assert json.loads(capsys.readouterr().out)["rows"] == []


async def test_delivered_pieces_without_their_row_are_left_for_a_manual_step(
    db: AsyncSession,
    capsys: pytest.CaptureFixture[str],
    create_user: Callable[..., Awaitable[User]],
    allow_lifecycle_drift: None,
) -> None:
    await _system_user(create_user)
    order = await seed.order(db, "delivered", ordered_date=seed.NOW, delivery_date=seed.NOW)
    line = await seed.line(
        db, order, "delivered", ordered_date=seed.NOW, quantity_delivered=10.0, booked=False
    )
    await db.commit()

    code = await admin.lifecycle_repair(_args(apply=True))

    assert code == 1
    document = json.loads(capsys.readouterr().out)
    assert document["rows"] == []
    [left] = document["left"]
    assert (left["table"], left["id"], left["field"], left["anomaly"]) == (
        "order_items",
        line.id,
        "quantity_delivered",
        True,
    )


async def test_apply_without_the_system_user_exits_three(
    db: AsyncSession, capsys: pytest.CaptureFixture[str], allow_lifecycle_drift: None
) -> None:
    await seed.order(db, "ordered")
    await db.commit()

    code = await admin.lifecycle_repair(_args(apply=True))

    captured = capsys.readouterr()
    assert code == 3
    assert captured.out == ""
    assert captured.err.startswith("lifecycle-repair failed: LookupError: ")


async def test_the_command_runs_as_its_own_process(
    db: AsyncSession, allow_lifecycle_drift: None
) -> None:
    ids = await _seed(db)
    env = {key: value for key, value in os.environ.items() if key != "ENV_FILE"}
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "src.bootstrap.cli.admin",
        "lifecycle-repair",
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
