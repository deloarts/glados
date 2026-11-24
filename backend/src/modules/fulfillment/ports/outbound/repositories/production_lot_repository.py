"""
Repository interface for the ProductionLot / LotStep / LotPosition
aggregate. Bundles all three in one protocol, mirroring how
IMadeItemRepository bundles MadeItem + its owned MadeItemProcess children.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable
from uuid import UUID

from src.modules.fulfillment.domain.entities.lot_event import LotEvent
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_position_provision import LotPositionProvision
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.services.scheduling import ExternalForecast


@dataclass
class ExternalWorkFilterDto:
    """The filters of the procurement list of external work. `today` is the
    tenant's day, against which an overdue send-out is judged."""

    today: date
    skip: int | None = None
    limit: int | None = None
    search: str | None = None
    fabrication_method_id: int | None = None
    # The supplier of the live line, or for a position without one the
    # default supplier of its outsourced method.
    supplier_id: int | None = None
    # Matched against the part number and the article name.
    part: str | None = None
    # Any of these lots, projects or products; the three filters AND.
    lot_ids: list[int] | None = None
    project_ids: list[int] | None = None
    product_ids: list[int] | None = None
    # Any of these stages and alerts, the values of
    # scheduling.external_work.ExternalWorkStage and ExternalWorkAlert.
    stages: list[str] | None = None
    alerts: list[str] | None = None
    # The forecast pickup, when the pieces can go out.
    ready_from: date | None = None
    ready_to: date | None = None
    latest_pickup_from: date | None = None
    latest_pickup_to: date | None = None
    # The day it is back: the supplier's date on the line, else the latest
    # delivery the walk counted.
    back_by_from: date | None = None
    back_by_to: date | None = None
    # Only positions already given to a supplier, a line of an order.
    only_with_supplier: bool = False
    # Only positions that cannot be ready by their latest pickup, or whose
    # latest pickup has passed while nothing was handed over.
    only_critical: bool = False


@dataclass
class LotFilterDto:
    skip: int | None = None
    limit: int | None = None
    ids: list[int] | None = None  # live row-sync: refetch specific rows, ignore paging
    search: str | None = None
    status: str | None = None
    statuses: list[str] | None = None
    made_item_id: int | None = None
    project_id: int | None = None
    project_number: str | None = None
    item_article_name: str | None = None
    item_part_number: str | None = None
    creator_id: int | None = None
    changed_by_id: int | None = None
    priority: str | None = None
    created_from: date | None = None
    created_to: date | None = None
    changed_from: date | None = None
    changed_to: date | None = None
    order_by: str | None = None
    order_dir: str | None = None
    # 'orders' | 'machines', only lots with at least one position actionable
    # for that Manage panel's mode (see lot.py's get_multi for the exact rule).
    # 'source', lot-level (not position-level): lots whose material source
    # can still be switched (see _filters.py's _actionable_lot_exists).
    actionable_for: str | None = None
    # Mutually exclusive (enforced in LotFilterParams, the HTTP schema this
    # DTO mirrors field-for-field: to_dto() is a blind **model_dump()).
    # "Could this lot still be routed to machine #X / pool #X / some pool";
    # see _filters.py's _coverable_lot_exists for the coverage semantics.
    coverable_by_machine_id: int | None = None
    coverable_by_pool_id: int | None = None
    coverable_by_any_pool: bool | None = None
    # "Needs Approval" list filter: SourceApprovalStatus value, an exact
    # match against the stored column (see production_lot_model.py).
    source_approval_status: str | None = None
    # Lot-level column filters. target_date_* compares the resolved target
    # date the lots table shows: the manual required_delivery_date, else the
    # earliest desired_delivery_date over the lot's made-item allocations
    # (see _filters.py's _target_date_expr). Bounds are inclusive calendar days.
    lot_number: str | None = None
    target_date_from: date | None = None
    target_date_to: date | None = None
    quantity_min: float | None = None
    quantity_max: float | None = None
    # Material source column filters. source_text searches the linked
    # bought / source / made source item's display fields. source_dimension
    # and source_type split that search along the two lines the source cell
    # shows: the dimension line (a source item's dimension, a bought item's
    # article name or order code, a made item's part number or article name)
    # and the type line (a source item's type or material). source_status is
    # a SourceItemDemandStatus value on the linked input demand;
    # source_delivery_* matches any order item behind that demand's
    # allocations (see _filters.py's _source_delivery_exists).
    source_text: str | None = None
    source_dimension: str | None = None
    source_type: str | None = None
    source_status: str | None = None
    source_delivery_from: date | None = None
    source_delivery_to: date | None = None
    # Step column filters. All of them must hold for ONE position of the lot
    # (a single EXISTS over lot_position, see _filters.py's _step_exists), the lot
    # then matches as a whole. The two method ids are mutually exclusive
    # (enforced in LotFilterParams); step_status is a display key mapped
    # back to stored status + kind in _filters.py's
    # _step_display_status_predicate; setup / per piece compare against the
    # position's summed step minutes.
    step_fabrication_method_id: int | None = None
    step_inspection_method_id: int | None = None
    step_status: str | None = None
    step_setup_min: int | None = None
    step_setup_max: int | None = None
    step_per_piece_min: float | None = None
    step_per_piece_max: float | None = None
    step_planned_start_from: date | None = None
    step_planned_start_to: date | None = None
    step_planned_end_from: date | None = None
    step_planned_end_to: date | None = None
    step_delivery_from: date | None = None
    step_delivery_to: date | None = None
    step_note: str | None = None
    # Only the rows that can give a Todo task on or before this day, the
    # tenant's horizon of the Todo page (see GetTodoSources). A wider set
    # than the tasks themselves: the page decides the buckets.
    todo_horizon: date | None = None


@runtime_checkable
class IProductionLotRepository(Protocol):
    async def get_by_id(self, id: int) -> ProductionLot | None: ...
    async def get_by_public_id(self, public_id: UUID) -> ProductionLot | None: ...
    async def get_by_id_for_update(self, id: int) -> ProductionLot | None:
        """Same as get_by_id but takes a row lock on the lot until the transaction ends, so
        two concurrent completions or provisions against one lot serialize instead of both
        computing the new total from the same stale read. SQLite ignores FOR UPDATE.

        The read refreshes the lot, its positions and their orders even where the session
        already held them, so a use case must work only with objects read after this call. A
        save of an entity read before the lock would write its stale values back."""
        ...

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[ProductionLot]:
        """The lots with their positions. With refresh, rows the session
        already holds are re-read, as the lifecycle reconciler needs."""
        ...

    async def lock_for_update(self, ids: list[int]) -> None:
        """Takes row locks on the lots, in ascending id order, held until the
        transaction ends (Postgres only; SQLite ignores FOR UPDATE), and
        re-reads them. The lifecycle lock plan calls it; a lot's lock also
        covers its positions."""
        ...

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        """Up to `limit` lot ids above `after_id`, ascending, for walking
        every lot in pages."""
        ...

    async def get_ids_with_external_work(self) -> list[int]:
        """The ids of every lot that is not terminal and has an open
        position of external work (scheduling.external_work), ascending."""
        ...

    async def get_external_work_page(
        self, filters: ExternalWorkFilterDto
    ) -> tuple[int, list[tuple[int, int]]]:
        """How many positions of external work match, and one page of them
        as (position id, lot id), by latest pickup, then forecast pickup,
        undated last."""
        ...

    async def get_multi(self, filters: LotFilterDto) -> tuple[int, list[ProductionLot]]: ...
    async def count_by_status(self) -> dict[str, int]:
        """How many rows the unfiltered list holds per stored status."""
        ...

    async def get_by_project_id(
        self, project_id: int, *, refresh: bool = False
    ) -> list[ProductionLot]:
        """Every lot of the project with its positions and steps, unpaged,
        by id. With refresh, rows the session already holds are read again."""
        ...

    async def lock_time_budgets(self, project_id: int) -> None:
        """Serializes the recomputes of one project's step time budgets
        until the caller's transaction ends, so a recompute reads what the
        one before it committed. It takes no row lock. SQLite ignores it."""
        ...

    async def save_step_time_budgets(self, budgets: Mapping[int, float | None]) -> None:
        """Writes the time budget per piece of each step id in `budgets`,
        that column alone, so a step edit committed since the steps were
        read keeps its other values."""
        ...

    async def get_force_completed_since(self, since: datetime) -> list[ProductionLot]:
        """The lots force-completed at or after `since`, oldest first."""
        ...

    async def save(self, lot: ProductionLot) -> ProductionLot: ...
    async def next_lot_number(self, template: str) -> str: ...
    async def get_raw_material_arrived_quantity(self, demand_id: int) -> float: ...
    async def get_raw_material_arrived_quantities(self, demand_ids: list[int]) -> dict[int, float]:
        """get_raw_material_arrived_quantity for many demands in a fixed
        number of queries. Every requested id has an entry, 0.0 when
        nothing has arrived for it."""
        ...

    async def reset_source_approval_for_setting_change(self, enabled: bool) -> int:
        """Bulk not_required<->pending flip backing UpdateProductionSettings'
        require_source_item_approval off/on backfill: one UPDATE, not a
        row-by-row load. See the SQLAlchemy implementation's docstring for
        the exact predicate and why no commit happens here."""
        ...

    # ── Steps ────────────────────────────────────────────────────────
    async def get_steps(self, lot_id: int) -> list[LotStep]: ...
    async def get_step_by_id(self, step_id: int) -> LotStep | None: ...
    async def save_step(self, step: LotStep) -> LotStep: ...
    async def delete_step(self, step: LotStep) -> None: ...
    async def reorder_steps(self, lot_id: int, ordered_step_ids: list[int]) -> list[LotStep]: ...

    # ── Positions ────────────────────────────────────────────────────
    async def get_positions(self, lot_id: int) -> list[LotPosition]: ...
    async def get_position_by_id(self, position_id: int) -> LotPosition | None: ...
    async def get_positions_by_ids(self, position_ids: list[int]) -> list[LotPosition]:
        """Batched get_position_by_id, enriched the same way. Ids that do
        not resolve are simply absent from the result."""
        ...

    async def save_position(self, position: LotPosition) -> LotPosition: ...
    async def save_position_forecasts(self, forecasts: list[ExternalForecast]) -> None:
        """Writes each forecast's planned pickup and delivery dates onto its
        position and flushes once, without reading the positions back. Ids
        that no longer exist are skipped and unchanged rows are not
        updated."""
        ...

    async def delete_position(self, position: LotPosition) -> None: ...
    async def get_quote_request_ids_of_positions(self, position_ids: list[int]) -> list[int]:
        """The quote requests with a line naming one of the positions, whose
        lines a delete of the position removes, ascending."""
        ...

    async def reorder_positions(
        self, lot_id: int, ordered_position_ids: list[int]
    ) -> list[LotPosition]: ...

    # ── Provisions (owned child of LotPosition) ──────────────────────────
    async def get_provisions(self, lot_position_id: int) -> list[LotPositionProvision]: ...
    async def save_provision(self, provision: LotPositionProvision) -> LotPositionProvision: ...
    # ── Events (owned child of ProductionLot; ISO 9001 audit trail) ──────
    async def get_events(self, lot_id: int) -> list[LotEvent]: ...
    async def record_event(self, event: LotEvent) -> LotEvent: ...
