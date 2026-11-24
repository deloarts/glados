"""Results of the procurement list of external work."""

from datetime import date
from datetime import datetime
from typing import Literal
from uuid import UUID

from src.modules.fulfillment.domain.services.scheduling.external_work import ExternalWorkAlert
from src.modules.fulfillment.domain.services.scheduling.external_work import ExternalWorkStage
from src.modules.fulfillment.domain.services.scheduling.external_work_explanation import (
    DateTermKind,
)
from src.modules.fulfillment.domain.services.scheduling.walk_context import LeadDaysSource
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.platform.application.dto.base import ResultModel

# Where the day a position comes back is from: the supplier's promise on
# the line, or the latest pickup plus the lead days.
BackBySource = Literal["supplier", "latest_pickup"]


class DateTermResult(ResultModel):
    """One line of how a date comes about (external_work_explanation)."""

    kind: DateTermKind
    date: date | None
    days: int | None
    minutes: int | None
    methods: list[dict[str, str]]
    source: LeadDaysSource | None
    reference: str


class ExternalWorkMethodResult(ResultModel):
    id: int
    name: dict[str, str]


class ExternalWorkRowResult(ResultModel):
    """One position of external work with what purchasing needs to send it
    out: what, from which lot, by when, to whom and where it stands."""

    position_id: int
    position_sequence: int
    kind: LotPositionKind
    position_status: LotPositionStatus
    lot_id: int
    lot_public_id: UUID
    lot_number: str
    project_id: int
    project_number: str
    # The product the lot's project belongs to, if any.
    product_id: int | None
    product_number: str | None
    made_item_id: int
    made_item_public_id: UUID | None
    part_number: str
    article_name: str
    revision: str
    quantity: float
    handed_over_quantity: float
    fabrication_methods: list[ExternalWorkMethodResult]
    lead_days: int
    # The pieces are there to go out now.
    ready_now: bool
    # The scheduler's forecast: when the pieces can go out and when they
    # are expected back.
    planned_pickup_date: date | None
    planned_delivery_date: date | None
    latest_pickup_date: date | None
    back_by_date: date | None
    back_by_source: BackBySource | None
    # Typed on the line by purchasing or the supplier, and the facts.
    expected_pickup_date: date | None
    ready_for_pickup_date: datetime | None
    order_item_id: int | None
    order_id: int | None
    order_number: str
    order_item_status: OrderItemStatus | None
    supplier_id: int | None
    supplier_name: str
    # The method's default supplier, a suggestion while there is no line.
    suggested_supplier_id: int | None
    suggested_supplier_name: str
    alert: ExternalWorkAlert | None
    # How the three dates come about, for the tooltips.
    ready_from_terms: list[DateTermResult]
    latest_pickup_terms: list[DateTermResult]
    back_by_terms: list[DateTermResult]
    # The terms do not end on the stored dates yet, since the schedule walk
    # has not caught up with a change.
    explanation_stale: bool


class ExternalWorkPageResult(ResultModel):
    total: int
    items: list[ExternalWorkRowResult]


class ExternalWorkQuery(ResultModel):
    """The list's filters as the client sends them; the use case adds the
    tenant's today."""

    skip: int | None = None
    limit: int | None = None
    search: str | None = None
    fabrication_method_id: int | None = None
    supplier_id: int | None = None
    part: str | None = None
    lot_ids: list[int] | None = None
    project_ids: list[int] | None = None
    product_ids: list[int] | None = None
    stages: list[ExternalWorkStage] | None = None
    alerts: list[ExternalWorkAlert] | None = None
    ready_from: date | None = None
    ready_to: date | None = None
    latest_pickup_from: date | None = None
    latest_pickup_to: date | None = None
    back_by_from: date | None = None
    back_by_to: date | None = None
    only_with_supplier: bool = False
    only_critical: bool = False
