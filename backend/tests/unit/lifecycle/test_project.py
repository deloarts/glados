"""
The project rules: a project with live work is not deleted, and only an
active project takes new demands and lots. Pure functions, no fakes.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.workspace.domain.entities.project import Project
from src.modules.workspace.domain.errors import ProjectDeleteBlockedError
from src.modules.workspace.domain.errors import ProjectInactiveError
from src.modules.workspace.domain.policies.project_activity import assert_project_active
from src.modules.workspace.domain.policies.project_activity import is_project_active
from src.modules.workspace.domain.services.lifecycle.project import assert_project_deletable
from src.modules.workspace.domain.value_objects.project_live_work import ProjectLiveWork
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus


def _project(status: ProjectStatus = ProjectStatus.ACTIVE, deleted: bool = False) -> Project:
    return Project(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        project_number="P-0815",
        status=status,
        deleted=deleted,
    )


def test_no_live_work_counts_nothing():
    work = ProjectLiveWork()
    assert work.total == 0
    assert work.describe() == ""


def test_the_counts_are_described_in_a_fixed_order_with_singular_and_plural():
    work = ProjectLiveWork(
        lots=2,
        production_orders=1,
        order_lines=3,
        bought_demands=1,
        made_demands=0,
        source_demands=2,
    )
    assert work.total == 9
    assert work.describe() == (
        "2 lots, 1 production order, 3 order lines, 1 bought item demand, 2 source item demands"
    )


def test_a_project_without_live_work_may_be_deleted():
    assert_project_deletable(_project(), ProjectLiveWork())


@pytest.mark.parametrize(
    ("work", "text"),
    [
        (ProjectLiveWork(lots=1), "1 lot"),
        (ProjectLiveWork(production_orders=2), "2 production orders"),
        (ProjectLiveWork(order_lines=1), "1 order line"),
        (ProjectLiveWork(bought_demands=1), "1 bought item demand"),
        (ProjectLiveWork(made_demands=3), "3 made item demands"),
        (ProjectLiveWork(source_demands=1), "1 source item demand"),
    ],
)
def test_any_live_work_refuses_the_delete_and_is_counted(work, text):
    with pytest.raises(ProjectDeleteBlockedError) as refused:
        assert_project_deletable(_project(), work)
    assert "P-0815" in str(refused.value)
    assert text in str(refused.value)


def test_an_active_project_takes_new_demands_and_lots():
    assert is_project_active(_project())
    assert_project_active(_project())


@pytest.mark.parametrize(
    ("status", "shown"),
    [
        (ProjectStatus.ON_HOLD, "on hold"),
        (ProjectStatus.COMPLETED, "completed"),
        (ProjectStatus.ARCHIVED, "archived"),
    ],
)
def test_a_project_that_is_not_active_takes_no_new_work(status, shown):
    assert not is_project_active(_project(status=status))
    with pytest.raises(ProjectInactiveError, match=f"is {shown};"):
        assert_project_active(_project(status=status))


def test_a_deleted_project_takes_no_new_work_whatever_its_status():
    deleted = _project(status=ProjectStatus.ACTIVE, deleted=True)
    assert not is_project_active(deleted)
    with pytest.raises(ProjectInactiveError, match="is deleted;"):
        assert_project_active(deleted)
