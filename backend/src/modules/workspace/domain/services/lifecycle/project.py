"""Rules of a project's lifecycle.

A project's status (active, on hold, completed, archived) has nothing to
derive it from; a user moves it through the intents of PROJECT_INTENTS. An
active project is held and a held one resumed, a project is completed or
archived only once its lots, production orders, order lines, demands and open
quote requests are all finished, and a completed or archived project can be
reopened. Deleting the project needs the same. Only an active project takes
new work: demands, lots, order lines moved onto it, external assignments and
reopened lines. Work already on a project that is not active can still be
ordered, delivered, corrected and closed, so it can be cleaned up; holding a
project with open work is therefore allowed.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.intent_table import HasStatus
from src.modules.platform.domain.services.intent_table import IntentRule
from src.modules.platform.domain.services.intent_table import IntentTable
from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.errors import ProjectDeleteBlockedError
from src.modules.workspace.domain.errors import ProjectStatusMoveBlockedError
from src.modules.workspace.domain.value_objects.project_live_work import ProjectLiveWork
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

# Singular and plural label of each count, in the order a message lists them.


def _without_live_work(_project: HasStatus, live_work: ProjectLiveWork) -> bool:
    return live_work.total == 0


_NO_LIVE_WORK = "no live lots, production orders, order lines, demands or open quote requests"
_ACTIVE = ProjectStatus.ACTIVE.value
_ON_HOLD = ProjectStatus.ON_HOLD.value
_COMPLETED = ProjectStatus.COMPLETED.value
_ARCHIVED = ProjectStatus.ARCHIVED.value

PROJECT_INTENTS = IntentTable[HasStatus, ProjectLiveWork](
    key="project",
    rules=(
        IntentRule(
            action=LifecycleAction.HOLD,
            allowed_from=(_ACTIVE,),
            effect="the project goes on hold and takes no new work; its open work goes on",
        ),
        IntentRule(
            action=LifecycleAction.RESUME,
            allowed_from=(_ON_HOLD,),
            effect="the project is active again and takes new work",
        ),
        IntentRule(
            action=LifecycleAction.COMPLETE,
            allowed_from=(_ACTIVE, _ON_HOLD),
            condition=_NO_LIVE_WORK,
            guard=_without_live_work,
            effect="the project is completed",
        ),
        IntentRule(
            action=LifecycleAction.ARCHIVE,
            allowed_from=(_ACTIVE, _ON_HOLD, _COMPLETED),
            condition=_NO_LIVE_WORK,
            guard=_without_live_work,
            effect="the project is archived",
        ),
        IntentRule(
            action=LifecycleAction.REOPEN,
            allowed_from=(_COMPLETED, _ARCHIVED),
            effect="the project is active again and takes new work",
        ),
        IntentRule(
            action=LifecycleAction.REMOVE,
            allowed_from=None,
            condition=_NO_LIVE_WORK,
            guard=_without_live_work,
            effect="the project is deleted",
        ),
    ),
)

# The status each status move of PROJECT_INTENTS sets.
PROJECT_STATUS_MOVES: dict[LifecycleAction, str] = {
    LifecycleAction.HOLD: _ON_HOLD,
    LifecycleAction.RESUME: _ACTIVE,
    LifecycleAction.COMPLETE: _COMPLETED,
    LifecycleAction.ARCHIVE: _ARCHIVED,
    LifecycleAction.REOPEN: _ACTIVE,
}


def project_status_move(current: str, target: str) -> LifecycleAction | None:
    """The intent that moves a project from `current` to `target`, None when
    the two are the same. A target no move of `current` reaches answers the
    first move into it, which the intent table then refuses on its status."""
    if current == target:
        return None
    into = [action for action, status in PROJECT_STATUS_MOVES.items() if status == target]
    for action in into:
        rule = PROJECT_INTENTS.rule_for(action)
        if rule is not None and rule.allowed_from is not None and current in rule.allowed_from:
            return action
    return into[0] if into else None


def assert_project_deletable(project: Project, live_work: ProjectLiveWork) -> None:
    """Refuses to delete a project that still has live work, and counts it.
    The remove rule of PROJECT_INTENTS decides."""
    rule = PROJECT_INTENTS.rule_for(LifecycleAction.REMOVE)
    if rule is not None and rule.guard(project, live_work):
        return
    raise ProjectDeleteBlockedError(
        f"Project {project.project_number!r} still has live work: {live_work.describe()}. "
        "Finish or cancel it before deleting the project."
    )


def assert_project_status_move(
    project: Project, target: str, live_work: ProjectLiveWork, actor: User
) -> LifecycleAction | None:
    """Refuses a status move the project's intent table does not allow now,
    and returns the intent of the move, None when the status stays. A move
    blocked by live work names the counts."""
    action = project_status_move(project.status, target)
    if action is None:
        return None
    refusal = PROJECT_INTENTS.check(action, project, live_work, actor)
    if refusal is None:
        return action
    current = project.status.replace("_", " ")
    wanted = target.replace("_", " ")
    if not refusal.by_status:
        raise ProjectStatusMoveBlockedError(
            f"Project {project.project_number!r} still has live work: {live_work.describe()}. "
            f"Finish or cancel it before the project is {wanted}."
        )
    raise ProjectStatusMoveBlockedError(
        f"Project {project.project_number!r} is {current} and cannot be set to {wanted}."
    )
