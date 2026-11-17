"""
Status enum for the Project aggregate.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class ProjectStatus(StrValueEnum):
    """Status of a Project, which a user moves through the intents of
    PROJECT_INTENTS (domain/services/lifecycle/project.py): an active project
    goes on hold and is resumed, is completed or archived once no work on it
    is live, and is reopened after being completed or archived. Every other
    move is refused."""

    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    ARCHIVED = "archived"

    @classmethod
    def default(cls) -> "ProjectStatus":
        return cls.ACTIVE
