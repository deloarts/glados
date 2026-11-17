"""
Pure domain entity. No SQLAlchemy, no Pydantic, no FastAPI.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING

from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.shared_kernel.domain.entities.base import Entity

if TYPE_CHECKING:
    from src.modules.catalogue.domain.entities.customer import Customer
    from src.modules.platform.domain.entities.user import User
    from src.modules.workspace.domain.entities.product import Product


@dataclass
class Project(Entity):
    created: datetime
    changed: datetime | None = None
    changes: list[str] = field(default_factory=list)
    deleted: bool = False

    status: ProjectStatus = ProjectStatus.ACTIVE
    designated_user_id: int = 0

    project_number: str = ""
    customer_id: int | None = None
    customer: "Customer | None" = None
    description: str | None = None

    product_id: int | None = None
    product: "Product | None" = None

    creator_id: int = 0
    creator: "User | None" = None
    changed_by_id: int | None = None
    changed_by: "User | None" = None

    # Manufacturing time (minutes) sold to the customer for this project,
    # entered by hand, apportioned across not-yet-estimated INTERNAL
    # LotSteps by time_budget_service.py to give the
    # scheduler something better than a bare 0 before real per-step
    # estimates exist.
    production_time_budget: int | None = None

    # Project-level default delivery dates used to prefill new demand items
    # of the matching kind (see create_demand_item use cases) and, on
    # request, propagated onto existing non-completed demands when changed
    # (see UpdateProject).
    required_delivery_date_made: date | None = None
    required_delivery_date_bought: date | None = None

    # Moves on every user edit of the project, so a client sends the value
    # it read and learns of a concurrent edit (domain/services/edit_version.py).
    edit_version: int = 0
