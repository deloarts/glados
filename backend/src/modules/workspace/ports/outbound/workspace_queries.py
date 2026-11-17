"""
What other modules read of Workspace: narrow query protocols over its
repositories, which the repositories satisfy as they are, and the filters
they take. Writes go through Workspace' use cases.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol
from typing import runtime_checkable
from uuid import UUID

from src.modules.workspace.domain.entities.meeting import Meeting
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.entities.product_device import ProductDevice
from src.modules.workspace.domain.entities.product_device_kind import ProductDeviceKind
from src.modules.workspace.domain.entities.product_variant import ProductVariant
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.value_objects.meeting import MeetingOwnerKind


@dataclass
class ProjectFilterDto:
    id: int | None = None
    ids: list[int] | None = None  # targeted fetch of specific rows by id, paging still applies
    project_number: str | None = None
    customer_id: int | None = None
    product_id: int | None = None
    description: str | None = None
    status: str | None = None
    designated_user_id: int | None = None
    creator_id: int | None = None
    changed_by_id: int | None = None
    # Calendar-day bounds, both inclusive.
    created_from: date | None = None
    created_to: date | None = None
    required_delivery_date_made_from: date | None = None
    required_delivery_date_made_to: date | None = None
    required_delivery_date_bought_from: date | None = None
    required_delivery_date_bought_to: date | None = None
    skip: int | None = None
    limit: int | None = None
    search: str | None = None
    order_by: str | None = None
    order_dir: str | None = None


@runtime_checkable
class IProductDeviceKindQueries(Protocol):
    async def get_many(self, include_archived: bool) -> list[ProductDeviceKind]:
        """Ordered by `sort_order`, then id, with their children."""
        ...


@runtime_checkable
class IProductDeviceQueries(Protocol):
    async def get_by_id(self, id: int) -> ProductDevice | None:
        """With its components, archived or not."""
        ...

    async def get_by_product(self, product_id: int, include_archived: bool) -> list[ProductDevice]:
        """With their components, ordered by UTF-8 name."""
        ...


@runtime_checkable
class IProductQueries(Protocol):
    async def get_by_id(self, id: int) -> Product | None:
        """Regardless of `archived`, references must resolve."""
        ...

    async def get_active(self, limit: int) -> list[Product]:
        """Live products marked active, by product number, at most `limit`."""
        ...


@runtime_checkable
class IProductVariantQueries(Protocol):
    async def get_by_product(self, product_id: int, include_archived: bool) -> list[ProductVariant]:
        """Ordered by `sort_order`, archived variants last."""
        ...


@runtime_checkable
class IProjectQueries(Protocol):
    async def get_by_id(self, id: int) -> Project | None: ...

    async def lock_for_share(self, ids: list[int]) -> None:
        """Locks the project rows in shared mode (SELECT ... FOR SHARE), in
        ascending id order, until the caller's transaction ends. A use case
        that creates a lot or a demand takes it before it checks that the
        project is active, so a concurrent delete waits for the creation and
        then counts it, while concurrent creations do not wait for each
        other. A project lock comes before any lifecycle row lock. SQLite
        ignores it."""
        ...

    async def get_multi(self, filters: ProjectFilterDto) -> tuple[int, list[Project]]: ...


@runtime_checkable
class IMeetingQueries(Protocol):
    async def get_by_public_id(self, public_id: UUID) -> Meeting | None:
        """The meeting with its attendees, deleted ones included."""
        ...


@dataclass(frozen=True)
class MeetingTodoRow:
    """An open todo of a meeting with what the todo page shows of it and
    needs to link to the meeting at its card."""

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


@runtime_checkable
class IMeetingTodoQueries(Protocol):
    async def list_open_todos_of_user(
        self, user_id: int, *, due_on_or_before: date
    ) -> list[MeetingTodoRow]:
        """The todos the user owns that are not done, of meetings that are
        valid and not deleted, due on or before the day or without a due
        date, by due date with the undated last."""
        ...
