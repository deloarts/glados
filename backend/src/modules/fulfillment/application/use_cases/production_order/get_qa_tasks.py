"""QA worklist read model: every production order on an inspection position,
with the part, lot and evidence state needed to triage it. A QA task is a
production order, so every existing action applies unchanged.

It is a dedicated endpoint because inspection-ness lives on the lot's
steps, which a client could only find by fetching every lot.
"""

from collections.abc import Callable
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import tzinfo
from typing import Any

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.production_order_dto import QaEvidenceFileResult
from src.modules.fulfillment.application.dto.production_order_dto import QaTaskResult
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.services.scheduling_context import (
    compute_conflicts_for_orders,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.production_order_file_category import (
    ProductionOrderFileCategory,
)
from src.modules.fulfillment.domain.value_objects.production_status import (
    TERMINAL_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_file_repository import (
    IProductionOrderFileRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    ProductionOrderFilterDto,
)
from src.modules.platform.application.mappers.user_mapper import UserMapper
from src.modules.platform.application.services.storage_asset import get_storage_url_best_effort
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.shared_kernel.domain.services.clock import as_utc
from src.shared_kernel.domain.services.clock import now_utc

# The states a QA engineer can still act on. Completed/canceled are opt-in
# via the filter, mirroring the list's "Show Completed"/"Show Canceled".
_OPEN_STATUSES = (
    ProductionOrderStatus.QUEUED,
    ProductionOrderStatus.IN_PROGRESS,
    ProductionOrderStatus.PAUSED,
)


class QaTaskFilterDto:
    """Server-side filters for the QA worklist. Defaults match the list's
    own defaults: open tasks only, and nothing that can't be worked yet."""

    def __init__(
        self,
        include_completed: bool = False,
        include_canceled: bool = False,
        include_future: bool = False,
        search: str | None = None,
        skip: int = 0,
        limit: int | None = None,
        order_by: str | None = None,
        order_dir: str = "asc",
        status: list[str] | None = None,
        inspection_method_ids: list[int] | None = None,
        lot_number: str | None = None,
        project_number: str | None = None,
        item_text: str | None = None,
        quantity_min: float | None = None,
        quantity_max: float | None = None,
        planned_start_from: date | None = None,
        planned_start_to: date | None = None,
        finished_from: date | None = None,
        finished_to: date | None = None,
        finished_by_ids: list[int] | None = None,
    ) -> None:
        self.include_completed = include_completed
        self.include_canceled = include_canceled
        self.include_future = include_future
        self.search = search
        # Paging is applied to the assembled worklist rather than pushed
        # into SQL; see GetQaTasks.execute for why it has to be.
        self.skip = skip
        self.limit = limit
        self.order_by = order_by
        self.order_dir = order_dir
        # Column filters of the worklist table, all applied in SQL so the
        # total and the pages stay consistent with what the query returns.
        self.status = status
        self.inspection_method_ids = inspection_method_ids
        self.lot_number = lot_number
        self.project_number = project_number
        self.item_text = item_text
        self.quantity_min = quantity_min
        self.quantity_max = quantity_max
        self.planned_start_from = planned_start_from
        self.planned_start_to = planned_start_to
        self.finished_from = finished_from
        self.finished_to = finished_to
        self.finished_by_ids = finished_by_ids

    def statuses(self) -> list[str]:
        # An explicit status pick from the column filter replaces the
        # completed and canceled toggles, so choosing "Completed" in the
        # column shows completed tasks without also flipping the toggle.
        if self.status:
            return list(self.status)
        result: list[str] = list(_OPEN_STATUSES)
        if self.include_completed:
            result.append(ProductionOrderStatus.COMPLETED)
        if self.include_canceled:
            result.append(ProductionOrderStatus.CANCELED)
        return result


class GetQaTasks:
    def __init__(
        self,
        order_repo: IProductionOrderRepository,
        lot_repo: IProductionLotRepository,
        machine_repo: IProductionMachineRepository,
        file_repo: IProductionOrderFileRepository,
        repos: SchedulingRepos,
        storage: IStoragePort | None = None,
    ) -> None:
        self._orders = order_repo
        self._lots = lot_repo
        self._machines = machine_repo
        self._files = file_repo
        self._repos = repos
        self._storage = storage

    async def execute(
        self, filters: QaTaskFilterDto, today: date | None = None
    ) -> tuple[int, list[QaTaskResult]]:
        """Returns (total, page). The future filter and the default order read
        can_start, which is computed rather than stored, so the worklist is
        assembled, filtered and sorted before slicing; _MAX_TASKS bounds it.
        `today` is a day of the tenant's timezone, the current one unless
        given, and a planned start counts on its day there."""
        _, orders = await self._orders.get_multi(
            ProductionOrderFilterDto(
                statuses=filters.statuses(),
                step_role=StepRole.INSPECTION,
                search=filters.search,
                limit=_MAX_TASKS,
                step_inspection_method_ids=filters.inspection_method_ids,
                lot_number=filters.lot_number,
                project_number=filters.project_number,
                item_text=filters.item_text,
                quantity_min=filters.quantity_min,
                quantity_max=filters.quantity_max,
                planned_start_from=filters.planned_start_from,
                planned_start_to=filters.planned_start_to,
                actual_end_from=filters.finished_from,
                actual_end_to=filters.finished_to,
                finished_by_ids=filters.finished_by_ids,
            )
        )
        if not orders:
            return 0, []

        # can_start and conflicts are computed here as a side effect on each
        # order entity (see compute_conflicts_for_orders), which is also what
        # the "future task" filter reads.
        conflicts_by_order = await compute_conflicts_for_orders(
            orders, self._repos, self._machines, lots_by_id=None
        )
        zone = await tenant_zone(self._repos.settings)
        if today is None:
            today = now_utc().astimezone(zone).date()

        lots_by_id = await self._load_lots({o.lot_id for o in orders})
        evidence_by_order = await self._load_evidence([o.id for o in orders])

        results: list[QaTaskResult] = []
        for order in orders:
            lot = lots_by_id.get(order.lot_id)
            if lot is None:
                continue
            position = next((p for p in lot.positions if p.id == order.lot_position_id), None)
            if position is None:
                continue
            step = next(
                (s for s in position.steps if s.role == StepRole.INSPECTION),
                None,
            )
            if step is None:
                # The EXISTS filter already guaranteed one; a position that
                # lost its inspection step between the two reads is skipped
                # rather than rendered as a QA task it no longer is.
                continue
            if not filters.include_future and _is_future(order, today, zone):
                continue
            results.append(
                self._to_result(order, lot, position, step, conflicts_by_order, evidence_by_order)
            )

        _sort(results, filters.order_by, filters.order_dir)
        # Total is the count AFTER the future filter, so the paginator counts
        # what the list can actually show rather than what the query matched.
        total = len(results)
        if filters.limit is None:
            return total, results[filters.skip :]
        return total, results[filters.skip : filters.skip + filters.limit]

    # ── Batched lookups ───────────────────────────────────────────────

    async def _load_lots(self, lot_ids: set[int]) -> dict[int, ProductionLot]:
        lots: dict[int, ProductionLot] = {}
        for lot_id in lot_ids:
            lot = await self._lots.get_by_id(lot_id)
            if lot is not None:
                lots[lot_id] = lot
        return lots

    async def _load_evidence(self, order_ids: list[int]) -> dict[int, list[QaEvidenceFileResult]]:
        """One query for every task's measurement reports, grouped by order.
        Storage URLs are resolved best-effort: with storage off they come
        back None, and the UI hides the column entirely in that case."""
        by_order: dict[int, list[QaEvidenceFileResult]] = {}
        for f in await self._files.get_by_item_ids(order_ids):
            if f.category != ProductionOrderFileCategory.MEASUREMENT_REPORT.value:
                continue
            url = (
                get_storage_url_best_effort(
                    self._storage,
                    f.storage_path,
                    context=f"production order file #{f.id}",
                    file_name=f.file_name,
                )
                if self._storage is not None
                else None
            )
            by_order.setdefault(f.production_order_id, []).append(
                QaEvidenceFileResult(
                    id=f.id,
                    file_name=f.file_name,
                    mime_type=f.mime_type,
                    category=f.category,
                    url=url,
                )
            )
        return by_order

    # ── Assembly ──────────────────────────────────────────────────────

    def _to_result(
        self,
        order: ProductionOrder,
        lot: ProductionLot,
        position: LotPosition,
        step: LotStep,
        conflicts_by_order: dict[int, list[str]],
        evidence_by_order: dict[int, list[QaEvidenceFileResult]],
    ) -> QaTaskResult:
        return QaTaskResult(
            id=order.id,
            public_id=order.public_id,
            production_order_number=order.production_order_number,
            status=order.status,
            priority=order.priority,
            quantity=order.quantity,
            quantity_completed=order.quantity_completed,
            planned_start=order.planned_start,
            planned_end=order.planned_end,
            actual_start=order.actual_start,
            actual_end=order.actual_end,
            finished_by=(
                UserMapper.to_public_result(operator)
                if (operator := _finished_by(order)) is not None
                else None
            ),
            can_start=order.can_start,
            conflicts=conflicts_by_order.get(order.id, []),
            inspection_method_id=step.inspection_method_id,
            inspection_method_name=(
                step.inspection_method_name.as_dict() if step.inspection_method_name else {}
            ),
            requires_evidence=bool(step.inspection_method_requires_evidence),
            has_evidence=bool(evidence_by_order.get(order.id)),
            evidence_files=evidence_by_order.get(order.id, []),
            lot_position_id=position.id,
            lot_position_sequence=position.sequence,
            lot_position_count=len(lot.positions),
            lot_id=lot.id,
            lot_number=lot.lot_number,
            lot_status=lot.status,
            made_item_id=lot.made_item_id,
            made_item_part_number=lot.made_item_part_number,
            made_item_article_name=lot.made_item_article_name,
            made_item_revision=lot.made_item_revision,
            made_item_material=lot.made_item_material,
            project_id=lot.project_id,
            project_number=lot.project_number or "",
            project_customer=lot.project_customer or "",
        )


# A QA worklist is a human's queue, not a data export, so this bounds one
# response without inventing pagination the UI doesn't need.
_MAX_TASKS = 500

# Aware, because it is compared with aware planned_start values.
_FAR_FUTURE = datetime.max.replace(tzinfo=UTC)


def _sort(results: list[QaTaskResult], order_by: str | None, order_dir: str) -> None:
    """Sorts in place on the server, since the list is paged. By default
    workable tasks come first, then by planned start, then by id.
    """
    if order_by is None:
        results.sort(key=lambda r: (not r.can_start, _planned_sort_key(r.planned_start), r.id))
        return

    key = _SORT_KEYS.get(order_by)
    if key is None:
        results.sort(key=lambda r: (not r.can_start, _planned_sort_key(r.planned_start), r.id))
        return
    # id as the tie-break for every explicit sort, so equal values (two lots
    # of the same part, a whole page of quantity 1) keep a stable order
    # instead of shuffling between refreshes.
    results.sort(key=lambda r: (key(r), r.id), reverse=order_dir == "desc")


# The sortable columns the views bar offers. Each returns a value that
# compares against its own kind only, so no mixed-type comparisons.
_SORT_KEYS: dict[str, Callable[[QaTaskResult], Any]] = {
    "planned": lambda r: _planned_sort_key(r.planned_start),
    "part": lambda r: r.made_item_part_number.casefold(),
    "lot": lambda r: r.lot_number.casefold(),
    "quantity": lambda r: r.quantity,
}


def _planned_sort_key(planned_start: datetime | None) -> datetime:
    """Undated tasks sort last."""
    return _FAR_FUTURE if planned_start is None else as_utc(planned_start)


def _finished_by(order: ProductionOrder) -> User | None:
    """The operator on the most recent completion, who actually did the
    inspection, as opposed to recorded_by, the session user who typed it
    in. None while nothing has been recorded yet."""
    if not order.completions:
        return None
    latest = max(order.completions, key=lambda c: (c.completion_date, c.id))
    return latest.operator


def _is_future(order: ProductionOrder, today: date, zone: tzinfo) -> bool:
    """A task nobody can act on yet, hidden by default.

    Terminal and started tasks are never future, so the completed and
    canceled toggles work on their own and a paused inspection, which the
    scheduler leaves undated, stays visible. Otherwise a task is future when
    Start would be refused, it has no planned start, or it starts on a day
    after today in the tenant's timezone `zone`.
    """
    # Finished one way or the other, so never "future".
    if order.status in TERMINAL_PRODUCTION_ORDER_STATUSES:
        return False
    if order.actual_start is not None:
        return False
    if not order.can_start:
        return True
    return (
        order.planned_start is None or as_utc(order.planned_start).astimezone(zone).date() > today
    )
