"""
The batch demand importers refuse a row whose demand would be refused: its
project is not active, or its item is one new work may not name. Validate
reports such a row as invalid with the reason, and commit refuses the batch.
No database, no HTTP.
"""

from dataclasses import replace

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.fulfillment.application.use_cases.bought_item_demand.batch_demand_items import (
    CommitBatchDemandRows,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.batch_demand_items import (
    ValidateBatchDemandRows,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.batch_demand_items import (
    CommitBatchMadeItemDemandRows,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.batch_demand_items import (
    ValidateBatchMadeItemDemandRows,
)
from src.modules.fulfillment.domain.errors import BatchDemandRowInvalidError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from tests.unit import test_batch_demand_items as bought
from tests.unit import test_batch_made_item_demand_items as made
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler


def _actor():
    return bought.make_user(permissions=[Permission.WRITE_DEMAND_ITEMS])


# ── Bought items ─────────────────────────────────────────────────────────


def _validate_bought(items, projects=None) -> ValidateBatchDemandRows:
    return ValidateBatchDemandRows(
        item_repo=bought.FakeBoughtItemRepo(items),
        project_repo=bought.FakeProjectRepo(projects or [bought.make_project()]),
        supplier_repo=bought.FakeSupplierRepo([bought.make_supplier()]),
    )


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"status": BoughtItemCatalogueStatus.INACTIVE}, "is inactive"),
        ({"status": BoughtItemCatalogueStatus.REPLACED}, "is replaced"),
        ({"pdm_sync_state": PdmSyncState.MISSING}, "is missing in PDM"),
    ],
)
async def test_a_bought_item_new_work_may_not_name_makes_the_row_invalid(changes, reason):
    item = replace(bought.make_item(), **changes)

    result = await _validate_bought([item]).execute(_actor(), [bought.make_row()])

    row = result.results[0]
    assert row.row_status == "invalid"
    assert any(reason in error for error in row.errors)
    assert not result.all_valid


async def test_a_bought_row_for_a_project_on_hold_is_invalid():
    project = replace(bought.make_project(), status=ProjectStatus.ON_HOLD)

    result = await _validate_bought([bought.make_item()], [project]).execute(
        _actor(), [bought.make_row()]
    )

    row = result.results[0]
    assert row.row_status == "invalid"
    assert row.resolved_project_id == project.id
    assert any("on hold" in error for error in row.errors)


async def test_an_unmatched_bought_row_also_names_the_inactive_project():
    project = replace(bought.make_project(), status=ProjectStatus.COMPLETED)

    result = await _validate_bought([], [project]).execute(_actor(), [bought.make_row()])

    row = result.results[0]
    assert row.row_status == "not_found"
    assert any("completed" in error for error in row.errors)


async def test_committing_a_bought_row_whose_demand_would_be_refused_creates_nothing():
    item = replace(bought.make_item(), status=BoughtItemCatalogueStatus.REPLACED)
    session = bought.FakeSession()
    demand_repo = bought.FakeDemandRepo()
    use_case = CommitBatchDemandRows(
        demand_repo=demand_repo,
        item_repo=bought.FakeBoughtItemRepo([item]),
        project_repo=bought.FakeProjectRepo([bought.make_project()]),
        supplier_repo=bought.FakeSupplierRepo([bought.make_supplier()]),
        uow=session,
        event_bus=bought.FakeEventBus(),
        reconciler=demand_reconciler(),
    )

    with pytest.raises(BatchDemandRowInvalidError, match="is replaced"):
        await use_case.execute(_actor(), [bought.make_row()])

    assert demand_repo.demands == {}


# ── Made items ───────────────────────────────────────────────────────────


def _validate_made(items, projects=None) -> ValidateBatchMadeItemDemandRows:
    return ValidateBatchMadeItemDemandRows(
        item_repo=made.FakeMadeItemRepo(items),
        project_repo=made.FakeProjectRepo(projects or [made.make_project()]),
    )


async def test_a_made_item_whose_file_is_missing_makes_the_row_invalid():
    item = replace(made.make_item(), pdm_sync_state=PdmSyncState.MISSING)

    result = await _validate_made([item]).execute(_actor(), [made.make_row()])

    row = result.results[0]
    assert row.row_status == "invalid"
    assert any("is missing in PDM" in error for error in row.errors)
    assert row.divergences == []


async def test_a_made_row_for_an_archived_project_is_invalid():
    project = replace(made.make_project(), status=ProjectStatus.ARCHIVED)

    result = await _validate_made([made.make_item()], [project]).execute(
        _actor(), [made.make_row()]
    )

    assert result.results[0].row_status == "invalid"


async def test_committing_a_made_row_for_a_project_on_hold_creates_nothing():
    project = replace(made.make_project(), status=ProjectStatus.ON_HOLD)
    demand_repo = made.FakeDemandRepo()
    use_case = CommitBatchMadeItemDemandRows(
        demand_repo=demand_repo,
        item_repo=made.FakeMadeItemRepo([made.make_item()]),
        project_repo=made.FakeProjectRepo([project]),
        uow=made.FakeSession(),
        event_bus=made.FakeEventBus(),
        reconciler=demand_reconciler(),
    )

    with pytest.raises(BatchDemandRowInvalidError, match="on hold"):
        await use_case.execute(_actor(), [made.make_row()])

    assert demand_repo.demands == {}
