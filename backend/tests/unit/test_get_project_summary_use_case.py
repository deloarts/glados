"""
Unit tests for GetProjectSummary.
`GET /projects/{project_id}/summary` has no integration test either, so
this is the use case's only coverage. The use case itself is a thin
existence check plus a pass-through to the project work port's summary
(a single aggregate SQL query in the real adapter), so the fake here
just returns a fixed dict and the tests confirm delegation, not the SQL.

Reuses make_project/FakeProjectRepository from tests/unit/test_project_use_cases.py.
"""

import pytest

from src.modules.workspace.application.use_cases.project.get_project_summary import (
    GetProjectSummary,
)
from src.modules.workspace.domain.errors import ProjectNotFoundError
from tests.unit.test_project_use_cases import FakeProjectRepository
from tests.unit.test_project_use_cases import make_project


class FakeOrderRepositoryForSummary:
    """Minimal fake: GetProjectSummary only ever calls get_summary()."""

    def __init__(self, summary: dict | None = None) -> None:
        self._summary = summary if summary is not None else {}
        self.calls: list[int] = []

    async def get_summary(self, project_id: int) -> dict:
        self.calls.append(project_id)
        return self._summary


class TestGetProjectSummary:
    async def test_unknown_project_is_not_found(self):
        use_case = GetProjectSummary(FakeProjectRepository(), FakeOrderRepositoryForSummary())

        with pytest.raises(ProjectNotFoundError):
            await use_case.execute(project_id=999)

    async def test_returns_the_repository_summary_verbatim(self):
        project = make_project(id=1)
        projects = FakeProjectRepository([project])
        summary = {
            "total_ordered_cost": 1200,
            "total_delivered_cost": 400,
            "order_count": 3,
            "cost_by_supplier": [{"supplier_id": 1, "supplier_name": "Acme", "cost": 1200}],
            "demand_counts": {"open": 2, "fulfilled": 1},
        }
        orders = FakeOrderRepositoryForSummary(summary)
        use_case = GetProjectSummary(projects, orders)

        result = await use_case.execute(project_id=1)

        assert result == summary
        assert orders.calls == [1]

    async def test_does_not_query_orders_when_project_is_missing(self):
        orders = FakeOrderRepositoryForSummary()
        use_case = GetProjectSummary(FakeProjectRepository(), orders)

        with pytest.raises(ProjectNotFoundError):
            await use_case.execute(project_id=42)

        assert orders.calls == []
