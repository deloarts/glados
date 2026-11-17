"""
Abstract interface for project persistence.
The application layer depends on this, never on the SQLAlchemy implementation.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.ports.outbound.workspace_queries import ProjectFilterDto


@runtime_checkable
class IProjectRepository(Protocol):
    async def get_by_id(self, id: int) -> Project | None: ...

    async def lock_for_update(self, id: int) -> None:
        """Locks the project row (SELECT ... FOR NO KEY UPDATE) until the
        caller's transaction ends. Deleting or updating a project takes it
        before it reads the project's work, so no lot or demand can be
        created for the project while it decides: it conflicts with
        lock_for_share. It does not conflict with the key share lock a
        foreign key check takes, so a row that merely references the project,
        inserted by a transaction that holds lifecycle rows this one waits
        for, cannot close a cycle with it. A project lock comes before any
        lifecycle row lock. SQLite ignores it."""
        ...

    async def lock_for_share(self, ids: list[int]) -> None:
        """Locks the project rows in shared mode (SELECT ... FOR SHARE), in
        ascending id order, until the caller's transaction ends. A use case
        that creates a lot or a demand takes it before it checks that the
        project is active, so a concurrent delete waits for the creation and
        then counts it, while concurrent creations do not wait for each
        other. A project lock comes before any lifecycle row lock. SQLite
        ignores it."""
        ...

    async def get_by_project_number(self, number: str) -> Project | None: ...

    async def get_by_product_id(self, product_id: int) -> list[Project]: ...

    async def get_by_designated_user_id(self, user_id: int) -> list[Project]: ...

    async def get_multi(self, filters: ProjectFilterDto) -> tuple[int, list[Project]]: ...

    async def save(self, project: Project) -> Project:
        """Insert (id == 0) or update (id > 0)."""
        ...

    async def delete(self, project: Project) -> None: ...
