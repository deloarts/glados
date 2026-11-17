"""
Whether a project accepts new work: the check every module runs before it
creates demands, lots or order lines for a project.
"""

from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.errors import ProjectInactiveError
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus


def is_project_active(project: Project) -> bool:
    """Whether the project takes new demands and lots."""
    return not project.deleted and project.status == ProjectStatus.ACTIVE


def assert_project_active(project: Project, *, work: str = "new demands and lots") -> None:
    """Refuses new work for a project that is deleted, on hold, completed or
    archived. `work` names what the caller puts on the project, for the
    message."""
    if is_project_active(project):
        return
    state = "deleted" if project.deleted else project.status.replace("_", " ")
    raise ProjectInactiveError(
        f"Project {project.project_number!r} is {state}; only an active project takes {work}."
    )
