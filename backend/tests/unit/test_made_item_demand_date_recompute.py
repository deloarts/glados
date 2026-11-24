"""A made item demand's desired delivery date is the target date of the lots
allocated to it that have none of their own, so changing it runs the
schedule walk after the edit is committed, and an edit that keeps the date
does not."""

from datetime import date

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.dto.made_item_demand_dto import UpdateMadeItemDemandCommand
from src.modules.fulfillment.application.use_cases.made_item_demand.update_demand_item import (
    UpdateDemandItem,
)
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.test_made_item_demand_use_cases import FakeDemandRepository
from tests.unit.test_made_item_demand_use_cases import FakeMadeItemRepository
from tests.unit.test_made_item_demand_use_cases import make_demand


class _Recompute:
    def __init__(self) -> None:
        self.walks = 0

    async def execute_all(self) -> None:
        self.walks += 1


def _use_case(desired: date | None) -> tuple[UpdateDemandItem, _Recompute]:
    demand = make_demand(id=1, creator_id=1, status=MadeItemDemandStatus.OPEN)
    demand.desired_delivery_date = desired
    demand_repo = FakeDemandRepository([demand])
    recompute = _Recompute()
    use_case = UpdateDemandItem(
        demand_repo,
        FakeMadeItemRepository(),
        uow=FakeUnitOfWork(),
        reconciler=demand_reconciler(made_demands=demand_repo),
        recompute_schedule=recompute,
    )
    return use_case, recompute


def _cmd(desired: date | None) -> UpdateMadeItemDemandCommand:
    return UpdateMadeItemDemandCommand(quantity=10.0, unit="pcs", desired_delivery_date=desired)


_OWNER = make_user(id=1, permissions=[Permission.WRITE_DEMAND_ITEMS])


async def test_a_changed_desired_date_runs_the_schedule_walk():
    use_case, recompute = _use_case(date(2026, 8, 20))

    await use_case.execute(actor=_OWNER, demand_id=1, cmd=_cmd(date(2026, 8, 27)))

    assert recompute.walks == 1


async def test_a_desired_date_set_for_the_first_time_runs_the_schedule_walk():
    use_case, recompute = _use_case(None)

    await use_case.execute(actor=_OWNER, demand_id=1, cmd=_cmd(date(2026, 8, 27)))

    assert recompute.walks == 1


async def test_an_edit_that_keeps_the_desired_date_runs_no_walk():
    use_case, recompute = _use_case(date(2026, 8, 20))

    await use_case.execute(actor=_OWNER, demand_id=1, cmd=_cmd(date(2026, 8, 20)))

    assert recompute.walks == 0
