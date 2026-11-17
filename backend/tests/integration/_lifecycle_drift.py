"""
The drift check the integration suite runs after every test: the stored
lifecycle fields of every aggregate the lifecycle reconciler writes must
equal their derivation. A test that stored a status by hand, or forgot to
register what it touched, leaves a row the check lists. The aggregates come
from RECONCILED_AGGREGATES at the moment of the check, so an aggregate joins
the check in the same line that hands it to the reconciler.
"""

from collections.abc import Collection

import pytest

from src.modules.fulfillment.adapters.outbound.persistence.lifecycle_store import (
    sql_lifecycle_repositories,
)
from src.modules.fulfillment.application.services import lifecycle_reconciler
from src.modules.fulfillment.application.services.lifecycle_drift import DriftRow
from src.modules.fulfillment.application.services.lifecycle_drift import LifecycleDriftReport
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal


def checked_aggregates() -> frozenset[LifecycleAggregate]:
    """The aggregates the reconciler writes, read when the check runs."""
    return lifecycle_reconciler.RECONCILED_AGGREGATES


async def lifecycle_drift_rows(aggregates: Collection[LifecycleAggregate]) -> list[DriftRow]:
    """The drift rows of the test database, in a session of their own."""
    async with SessionLocal() as db:
        report = await LifecycleDriftReport(sql_lifecycle_repositories(db)).run(aggregates)
    return report.rows


def drift_failure(rows: list[DriftRow]) -> str:
    lines = [
        f"{row.table} #{row.id} {row.field}: stored {row.stored}, derived {row.derived} "
        f"({row.rule})"
        for row in rows
    ]
    return (
        "Lifecycle drift after the test: a stored lifecycle field disagrees with its "
        "derivation. Record facts and intents and register them with the lifecycle "
        "reconciler instead of storing a status, or request `allow_lifecycle_drift` "
        "in a test that leaves such rows on purpose.\n" + "\n".join(lines)
    )


async def assert_no_lifecycle_drift(aggregates: Collection[LifecycleAggregate]) -> None:
    """Fails the test with the drift rows of the given aggregates; does
    nothing without aggregates."""
    if not aggregates:
        return
    rows = await lifecycle_drift_rows(aggregates)
    if rows:
        pytest.fail(drift_failure(rows), pytrace=False)
