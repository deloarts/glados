"""Use cases for retrieving production lots with conflict computation for their production
orders."""

from src.modules.fulfillment.application.dto.production_lot_dto import LotResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotSummaryResult
from src.modules.fulfillment.application.mappers.production_lot_mapper import LotMapper
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.services.scheduling_context import (
    compute_conflicts_for_orders,
)
from src.modules.fulfillment.application.services.scheduling_context import (
    compute_schedule_explanations_for_orders,
)
from src.modules.fulfillment.application.services.scheduling_context import (
    describe_lot_target_dates,
)
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.domain.services.scheduling import (
    resolve_position_lead_days_with_source,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    IMachinePoolRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    LotFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User

_LEAD_DAYS_KINDS = frozenset({LotPositionKind.EXTERNAL, LotPositionKind.MIXED})


def _lead_days_by_position_id(
    lots: list[ProductionLot], default_external_lead_days: int
) -> dict[int, tuple[int, str]]:
    """One (lead_days, source) pair per EXTERNAL/MIXED position across
    `lots` (see scheduling.resolve_position_lead_days_with_source),
    keyed by position id. An INTERNAL/UNASSIGNED position never carries an
    external lead time and is left out entirely."""
    result: dict[int, tuple[int, str]] = {}
    for lot in lots:
        for position in lot.positions:
            if position.kind not in _LEAD_DAYS_KINDS:
                continue
            result[position.id] = resolve_position_lead_days_with_source(
                position.steps,
                position.order_item_supplier_external_lead_time_days,
                default_external_lead_days,
            )
    return result


class GetLot:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        repos: SchedulingRepos,
        machine_repo: IProductionMachineRepository,
        pool_repo: IMachinePoolRepository | None = None,
    ) -> None:
        self._lots = lot_repo
        self._repos = repos
        self._machines = machine_repo
        self._pools = pool_repo

    async def execute(self, lot_id: int, actor: User | None = None) -> LotResult:
        """The lot with its production orders' conflicts, and with an actor
        their actions."""
        lot = found_or_raise(
            await self._lots.get_by_id(lot_id), LotNotFoundError, f"Lot #{lot_id} not found."
        )
        orders = [o for position in lot.positions for o in position.production_orders]
        conflicts_by_order_id = await compute_conflicts_for_orders(
            orders,
            self._repos,
            self._machines,
            lots_by_id={lot.id: lot},
            pool_repo=self._pools,
            actor=actor,
        )
        return LotMapper.to_result(lot, conflicts_by_order_id)

    async def changelog(self, lot_id: int) -> list[str]:
        """The lot's changelog lines, without the conflict computation of
        execute; a missing id raises LotNotFoundError, as execute does."""
        lot = found_or_raise(
            await self._lots.get_by_id(lot_id), LotNotFoundError, f"Lot #{lot_id} not found."
        )
        return lot.changes


class GetLots:
    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        repos: SchedulingRepos,
        machine_repo: IProductionMachineRepository,
        settings_repo: IFulfillmentSettingsRepository,
        pool_repo: IMachinePoolRepository | None = None,
    ) -> None:
        self._lots = lot_repo
        self._repos = repos
        self._machines = machine_repo
        self._pools = pool_repo
        self._settings = settings_repo

    async def execute(self, filters: LotFilterDto) -> tuple[int, list[LotSummaryResult]]:
        total, lots = await self._lots.get_multi(filters)
        # One conflict pass for the whole page, seeded with the lots just
        # loaded so it doesn't turn around and re-fetch them one at a time.
        # Same computation GetLot runs for a single lot, so a step's
        # conflict icon reads identically in the list and the detail view.
        orders = [
            o for lot in lots for position in lot.positions for o in position.production_orders
        ]
        lots_by_id = {lot.id: lot for lot in lots}
        conflicts_by_order_id = await compute_conflicts_for_orders(
            orders, self._repos, self._machines, lots_by_id=lots_by_id, pool_repo=self._pools
        )
        explanations_by_order_id = await compute_schedule_explanations_for_orders(
            orders, self._repos, self._machines, lots_by_id=lots_by_id, pool_repo=self._pools
        )
        lead_days_by_position_id = _lead_days_by_position_id(
            lots, (await self._settings.get_production()).default_external_lead_days
        )
        target_date_by_lot_id = await describe_lot_target_dates(lots, self._repos)
        return total, [
            LotMapper.to_summary(
                lot,
                conflicts_by_order_id,
                explanations_by_order_id,
                lead_days_by_position_id,
                target_date_by_lot_id,
            )
            for lot in lots
        ]


class GetLotsByIds:
    """Bulk full-lot read backing GET /production-lots/bulk: the schedule
    board needs full LotResult objects (positions incl. sequence/steps/
    supplier_name) for a working set of lot ids in one request, which the
    summary-shaped GetLots can't provide (LotSummaryPositionResponse omits
    those fields). Mirrors GetLots' conflict-computation batching, just
    against IProductionLotRepository.get_by_ids instead of get_multi:
    ids that don't exist are silently absent from get_by_ids' result and
    therefore from this one too, never a 404 (see the endpoint docstring).
    Result order follows get_by_ids, not the input `ids` order."""

    def __init__(
        self,
        lot_repo: IProductionLotRepository,
        repos: SchedulingRepos,
        machine_repo: IProductionMachineRepository,
        pool_repo: IMachinePoolRepository | None = None,
    ) -> None:
        self._lots = lot_repo
        self._repos = repos
        self._machines = machine_repo
        self._pools = pool_repo

    async def execute(self, ids: list[int], actor: User | None = None) -> list[LotResult]:
        lots = await self._lots.get_by_ids(ids)
        orders = [
            o for lot in lots for position in lot.positions for o in position.production_orders
        ]
        conflicts_by_order_id = await compute_conflicts_for_orders(
            orders,
            self._repos,
            self._machines,
            lots_by_id={lot.id: lot for lot in lots},
            pool_repo=self._pools,
            actor=actor,
        )
        return [LotMapper.to_result(lot, conflicts_by_order_id) for lot in lots]
