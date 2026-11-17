"""
The rows the Todo page builds its tasks from, in the shapes of their list
endpoints.
"""

from datetime import date

from pydantic import Field

from src.modules.fulfillment.adapters.inbound.api.schemas.bought_item_demand_schema import (
    DemandItemResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_demand_schema import (
    MadeItemDemandResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import OrderResponse
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    LotSummaryResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.source_item_demand_schema import (
    SourceItemDemandResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.workspace.domain.value_objects.meeting import MeetingOwnerKind


class MeetingTodoSourceResponse(ResponseModel):
    """An open todo of a valid meeting that the user owns. The task links to
    the meeting page of the owner, `/workspace/projects/:owner_id/meeting-notes/:meeting_id`
    or the product equivalent, at the card."""

    todo_id: int
    title: str
    due_date: date | None
    meeting_id: int
    meeting_number: str
    meeting_name: str
    owner_kind: MeetingOwnerKind
    owner_id: int
    card_id: int
    card_scope: str | None


class TodoSourcesResponse(ResponseModel):
    """Every order, demand and lot that can give a Todo task on or before
    `horizon`, a day in the tenant's timezone, as their list endpoints show
    them but without the lifecycle actions. Rows that can never give a task,
    such as delivered orders or fulfilled demands, are left out. The meeting
    todos are the signed-in user's open ones, due by `horizon` or undated."""

    horizon: date
    orders: list[OrderResponse] = Field(default_factory=list)
    bought_demands: list[DemandItemResponse] = Field(default_factory=list)
    made_demands: list[MadeItemDemandResponse] = Field(default_factory=list)
    source_demands: list[SourceItemDemandResponse] = Field(default_factory=list)
    lots: list[LotSummaryResponse] = Field(default_factory=list)
    meeting_todos: list[MeetingTodoSourceResponse] = Field(default_factory=list)
