"""
Commands and results of the demand items of bought items, the procurement
pipeline and the batch demand import.
"""

from datetime import date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult


class CreateDemandItemCommand(BaseModel):
    item_id: int = Field(..., gt=0)
    project_id: int = Field(..., gt=0)
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., min_length=1)
    items_per_unit: float = Field(default=1.0, gt=0)
    high_priority: bool = False
    notify_on_delivery: bool = False
    note: str | None = None
    desired_delivery_date: date | None = None


class UpdateDemandItemCommand(BaseModel):
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., min_length=1)
    items_per_unit: float = Field(default=1.0, gt=0)
    high_priority: bool = False
    notify_on_delivery: bool = False
    note: str | None = None
    desired_delivery_date: date | None = None


class DemandItemResult(ResultBase):
    status: str
    # The lifecycle actions the reading user may take now, from the intent
    # table (lifecycle/intents.py); empty where no user is known.
    actions: list[str] = Field(default_factory=list)
    created: datetime
    changed: datetime | None
    quantity: float
    unit: str
    items_per_unit: float
    high_priority: bool
    notify_on_delivery: bool
    note: str | None
    desired_delivery_date: date | None
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    item_id: int
    item_order_code_1: str
    item_article_name: str
    item: BoughtItemResult | None = None
    project_id: int
    project_number: str
    project_customer: str
    project_description: str
    project_status: str
    bucket_id: int | None
    # Lifecycle intents, read-only (see the BoughtItemDemandItem entity).
    canceled_at: datetime | None = None
    fulfilled_manually_at: datetime | None = None


class PipelineRowResult(BaseModel):
    demand_item_id: int
    status: str
    high_priority: bool
    item_id: int
    item_order_code_1: str
    item_article_name: str
    project_id: int
    project_number: str
    unit: str
    total: float
    allocated: float
    ordered: float
    delivered: float
    fulfilled_from_stock: float
    remaining: float
    is_fully_allocated: bool
    is_fully_delivered: bool
    supplier_names: list[str] = Field(default_factory=list)
    order_numbers: list[str] = Field(default_factory=list)
    expected_delivery_dates: list[date] = Field(default_factory=list)


class PipelineResult(BaseModel):
    items: list[PipelineRowResult] = Field(default_factory=list)


class BatchDemandRowInput(BaseModel):
    """
    Intentionally permissive (no min_length/gt constraints on the row's own data):
    a blank/garbled cell in one Excel row must surface as a per-row 'invalid' status
    with a specific message, not reject the entire batch request with a 422.
    """

    row_index: int
    project_number: str | None = None
    quantity: float | None = None
    unit: str | None = None
    part_number: str | None = None
    article_name: str | None = None
    order_code: str | None = None
    manufacturer_name: str | None = None
    desired_delivery_date: date | None = None
    note: str | None = None


class FieldDivergence(BaseModel):
    field: Literal["article_name", "manufacturer_name", "order_code", "part_number"]
    db_value: str | None
    file_value: str | None


class RowValidationResult(BaseModel):
    row_index: int
    row_status: Literal["matched", "not_found", "ambiguous", "unresolved_reference", "invalid"]
    match_source: Literal["part_number", "order_code_manufacturer"] | None = None
    matched_item: BoughtItemResult | None = None
    divergences: list[FieldDivergence] = Field(default_factory=list)
    resolved_project_id: int | None = None
    errors: list[str] = Field(default_factory=list)


class ValidateBatchDemandsResult(BaseModel):
    results: list[RowValidationResult]
    all_valid: bool


class CommitBatchDemandsResult(BaseModel):
    created_demand_ids: list[int] = Field(default_factory=list)
