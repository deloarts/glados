"""
The batch demand importers take their rows through a permissive schema, so
a quantity of NaN or infinity reaches the row validation. Validate reports
such a row as invalid with its own message, the other rows stay valid, and
commit refuses the batch without creating a demand. No database, no HTTP.
"""

import pytest

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
from tests.unit import test_batch_demand_items as bought
from tests.unit import test_batch_made_item_demand_items as made
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler

NON_FINITE = [float("nan"), float("inf"), float("-inf")]
MESSAGE = "Quantity must be a finite number."


def _actor():
    return bought.make_user(permissions=[Permission.WRITE_DEMAND_ITEMS])


@pytest.mark.parametrize("quantity", NON_FINITE)
async def test_a_bought_row_with_a_non_finite_quantity_is_invalid(quantity: float) -> None:
    use_case = ValidateBatchDemandRows(
        item_repo=bought.FakeBoughtItemRepo([bought.make_item()]),
        project_repo=bought.FakeProjectRepo([bought.make_project()]),
        supplier_repo=bought.FakeSupplierRepo([bought.make_supplier()]),
    )

    result = await use_case.execute(
        _actor(), [bought.make_row(quantity=quantity), bought.make_row(row_index=1)]
    )

    refused, fine = result.results
    assert refused.row_status == "invalid"
    assert refused.errors == [MESSAGE]
    assert fine.row_status != "invalid"
    assert not result.all_valid


@pytest.mark.parametrize("quantity", NON_FINITE)
async def test_committing_a_bought_row_with_a_non_finite_quantity_creates_nothing(
    quantity: float,
) -> None:
    demand_repo = bought.FakeDemandRepo()
    use_case = CommitBatchDemandRows(
        demand_repo=demand_repo,
        item_repo=bought.FakeBoughtItemRepo([bought.make_item()]),
        project_repo=bought.FakeProjectRepo([bought.make_project()]),
        supplier_repo=bought.FakeSupplierRepo([bought.make_supplier()]),
        uow=bought.FakeSession(),
        event_bus=bought.FakeEventBus(),
        reconciler=demand_reconciler(),
    )

    with pytest.raises(BatchDemandRowInvalidError, match=MESSAGE):
        await use_case.execute(_actor(), [bought.make_row(quantity=quantity)])

    assert demand_repo.demands == {}


@pytest.mark.parametrize("quantity", NON_FINITE)
async def test_a_made_row_with_a_non_finite_quantity_is_invalid(quantity: float) -> None:
    use_case = ValidateBatchMadeItemDemandRows(
        item_repo=made.FakeMadeItemRepo([made.make_item()]),
        project_repo=made.FakeProjectRepo([made.make_project()]),
    )

    result = await use_case.execute(
        _actor(), [made.make_row(quantity=quantity), made.make_row(row_index=1)]
    )

    refused, fine = result.results
    assert refused.row_status == "invalid"
    assert refused.errors == [MESSAGE]
    assert fine.row_status != "invalid"
    assert not result.all_valid


@pytest.mark.parametrize("quantity", NON_FINITE)
async def test_committing_a_made_row_with_a_non_finite_quantity_creates_nothing(
    quantity: float,
) -> None:
    demand_repo = made.FakeDemandRepo()
    use_case = CommitBatchMadeItemDemandRows(
        demand_repo=demand_repo,
        item_repo=made.FakeMadeItemRepo([made.make_item()]),
        project_repo=made.FakeProjectRepo([made.make_project()]),
        uow=made.FakeSession(),
        event_bus=made.FakeEventBus(),
        reconciler=demand_reconciler(),
    )

    with pytest.raises(BatchDemandRowInvalidError, match=MESSAGE):
        await use_case.execute(_actor(), [made.make_row(quantity=quantity)])

    assert demand_repo.demands == {}
