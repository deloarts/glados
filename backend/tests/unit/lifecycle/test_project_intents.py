"""The status moves of a project's intent table: which intent a requested
status means, and which moves its status and its live work allow."""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.errors import ProjectStatusMoveBlockedError
from src.modules.workspace.domain.services.lifecycle.project import PROJECT_INTENTS
from src.modules.workspace.domain.services.lifecycle.project import assert_project_status_move
from src.modules.workspace.domain.services.lifecycle.project import project_status_move
from src.modules.workspace.domain.value_objects.project_live_work import ProjectLiveWork
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction as A
from tests.factories import make_user

NOW = datetime(2026, 10, 1, tzinfo=UTC)
ACTOR = make_user(permissions=[])
LIVE = ProjectLiveWork(order_lines=2)


def _project(status: ProjectStatus) -> Project:
    return Project(id=1, created=NOW, project_number="P-1", status=status)


@pytest.mark.parametrize(
    ("current", "target", "action"),
    [
        (ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD, A.HOLD),
        (ProjectStatus.ON_HOLD, ProjectStatus.ACTIVE, A.RESUME),
        (ProjectStatus.COMPLETED, ProjectStatus.ACTIVE, A.REOPEN),
        (ProjectStatus.ARCHIVED, ProjectStatus.ACTIVE, A.REOPEN),
        (ProjectStatus.ON_HOLD, ProjectStatus.COMPLETED, A.COMPLETE),
        (ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED, A.ARCHIVE),
        (ProjectStatus.ACTIVE, ProjectStatus.ACTIVE, None),
    ],
)
def test_a_requested_status_names_its_move(current, target, action):
    assert project_status_move(current, target) == action


@pytest.mark.parametrize(
    ("status", "work", "offered"),
    [
        (ProjectStatus.ACTIVE, ProjectLiveWork(), {A.HOLD, A.COMPLETE, A.ARCHIVE, A.REMOVE}),
        (ProjectStatus.ACTIVE, LIVE, {A.HOLD}),
        (ProjectStatus.ON_HOLD, LIVE, {A.RESUME}),
        (ProjectStatus.ON_HOLD, ProjectLiveWork(), {A.RESUME, A.COMPLETE, A.ARCHIVE, A.REMOVE}),
        (ProjectStatus.COMPLETED, ProjectLiveWork(), {A.ARCHIVE, A.REOPEN, A.REMOVE}),
        (ProjectStatus.ARCHIVED, ProjectLiveWork(), {A.REOPEN, A.REMOVE}),
    ],
)
def test_the_offered_moves_follow_the_status_and_the_live_work(status, work, offered):
    assert set(PROJECT_INTENTS.allowed_actions(_project(status), work, ACTOR)) == offered


def test_live_work_blocks_completing_with_the_counts():
    with pytest.raises(ProjectStatusMoveBlockedError, match="2 order lines"):
        assert_project_status_move(_project(ProjectStatus.ACTIVE), "completed", LIVE, ACTOR)


def test_holding_passes_with_live_work():
    assert (
        assert_project_status_move(_project(ProjectStatus.ACTIVE), "on_hold", LIVE, ACTOR) == A.HOLD
    )


def test_a_move_the_status_does_not_start_is_refused_by_name():
    with pytest.raises(
        ProjectStatusMoveBlockedError, match="is completed and cannot be set to on hold"
    ):
        assert_project_status_move(
            _project(ProjectStatus.COMPLETED), "on_hold", ProjectLiveWork(), ACTOR
        )
