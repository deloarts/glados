"""
Input commands and output results for project use cases.
These cross the application boundary, not the same as API schemas.
"""

from datetime import date
from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.application.dto.customer_dto import CustomerResult
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult
from src.modules.workspace.application.dto.product_dto import ProductResult
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus

# ── Commands (inbound) ────────────────────────────────────────────────


class CreateProjectCommand(BaseModel):
    project_number: str
    customer_id: int | None = None
    product_id: int | None = None
    description: str | None = None
    designated_user_id: int | None = None
    status: ProjectStatus = ProjectStatus.ACTIVE
    production_time_budget: int | None = None
    required_delivery_date_made: date | None = None
    required_delivery_date_bought: date | None = None


class UpdateProjectCommand(BaseModel):
    project_number: str
    customer_id: int | None = None
    product_id: int | None = None
    description: str | None = None
    designated_user_id: int | None = None
    status: ProjectStatus | None = None
    production_time_budget: int | None = None
    required_delivery_date_made: date | None = None
    required_delivery_date_bought: date | None = None
    # Bulk-propagate the corresponding date onto all non-completed demands of
    # this project when set (see UpdateProject), ignored unless the
    # matching date field also changed to a new non-null value.
    propagate_delivery_date_made: bool = False
    propagate_delivery_date_bought: bool = False
    # The edit version the client read; a project edited since answers 409.
    expected_edit_version: int | None = None


# ── Results (outbound) ────────────────────────────────────────────────


class ProjectLiveWorkResult(BaseModel):
    """The project's unfinished work per kind (ProjectLiveWork)."""

    lots: int = 0
    production_orders: int = 0
    order_lines: int = 0
    bought_demands: int = 0
    made_demands: int = 0
    source_demands: int = 0
    quote_requests: int = 0


class ProjectResult(ResultBase):
    project_number: str
    customer_id: int | None
    customer: CustomerResult | None
    product_id: int | None
    product: ProductResult | None
    description: str | None
    status: str
    designated_user_id: int
    created: datetime
    changed: datetime | None
    changes: list[str] = Field(default_factory=list)
    deleted: bool
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    production_time_budget: int | None
    required_delivery_date_made: date | None
    required_delivery_date_bought: date | None
    edit_version: int = 0
    # The status moves and the delete the reading user may take now, from
    # the project intent table, and the live work that blocks completing,
    # archiving and deleting. Filled by the web reads only.
    actions: list[str] = Field(default_factory=list)
    live_work: ProjectLiveWorkResult | None = None
