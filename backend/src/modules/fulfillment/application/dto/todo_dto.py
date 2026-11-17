"""
The rows the Todo page builds its tasks from.
"""

from datetime import date

from pydantic import Field

from src.modules.fulfillment.application.dto.bought_item_demand_dto import DemandItemResult
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemDemandItemResult
from src.modules.fulfillment.application.dto.order_dto import OrderResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotSummaryResult
from src.modules.fulfillment.application.dto.source_item_demand_dto import SourceItemDemandResult
from src.modules.platform.application.dto.base import ResultModel
from src.modules.workspace.domain.value_objects.meeting import MeetingOwnerKind


class MeetingTodoSourceResult(ResultModel):
    """An open todo of a valid meeting that the user owns, with what the
    task shows and the meeting page it links to at the card."""

    todo_id: int
    title: str
    due_date: date | None
    meeting_id: int
    meeting_number: str
    meeting_name: str
    # The project or product whose meeting page the task opens.
    owner_kind: MeetingOwnerKind
    owner_id: int
    card_id: int
    card_scope: str | None


class TodoSourcesResult(ResultModel):
    """Every order, demand and lot that can give a Todo task on or before
    `horizon`, in the shapes of their list endpoints without the lifecycle
    actions, and the user's own open meeting todos due by then or without a
    due date. The page builds the tasks and their buckets from these rows
    exactly as it did from the whole lists, so a row left out here is one
    that could never give a task."""

    horizon: date
    orders: list[OrderResult] = Field(default_factory=list)
    bought_demands: list[DemandItemResult] = Field(default_factory=list)
    made_demands: list[MadeItemDemandItemResult] = Field(default_factory=list)
    source_demands: list[SourceItemDemandResult] = Field(default_factory=list)
    lots: list[LotSummaryResult] = Field(default_factory=list)
    meeting_todos: list[MeetingTodoSourceResult] = Field(default_factory=list)
