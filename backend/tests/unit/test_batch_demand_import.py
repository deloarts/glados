"""
The helpers the bought and made item batch demand importers share: the
quantity check, the row status precedence, the demand refusals and the
per-project shared lock of the commit.
"""

import math
from types import SimpleNamespace
from typing import Any

import pytest

from src.modules.fulfillment.application.services import batch_demand_import
from src.modules.fulfillment.application.services.batch_demand_import import LockedProjects
from src.modules.fulfillment.application.services.batch_demand_import import decide_row_status
from src.modules.fulfillment.application.services.batch_demand_import import new_demand_refusals
from src.modules.fulfillment.application.services.batch_demand_import import quantity_error
from src.modules.platform.application.services.import_text import norm
from src.modules.workspace.domain.errors import ProjectNotFoundError


@pytest.mark.parametrize(
    ("quantity", "unit", "error"),
    [
        (2.0, None, None),
        (2.5, "M", None),
        (2.5, None, "Quantity must be a whole number."),
        (2.5, "pcs", "Quantity must be a whole number."),
        (math.nan, None, "Quantity must be a finite number."),
        (math.inf, "M", "Quantity must be a finite number."),
        (0, None, "Quantity must be greater than 0."),
        (-1, None, "Quantity must be greater than 0."),
        (None, None, "Quantity must be greater than 0."),
    ],
)
def test_batch_demand_import_quantity_error(
    quantity: float | None, unit: str | None, error: str | None
) -> None:
    # Without a unit the row counts pieces, as a made item demand always does.
    assert quantity_error(quantity, unit) == error


@pytest.mark.parametrize("quantity", [0.0000004, 0.000001, 1e12, 5e12])
def test_batch_demand_import_quantity_error_refuses_what_the_columns_cannot_store(
    quantity: float,
) -> None:
    error = quantity_error(quantity, "M")

    assert error is not None
    assert "count as nothing" in error or "must be below" in error


def test_batch_demand_import_norm_strips_and_lowers() -> None:
    assert norm("  AbC ") == "abc"
    assert norm(None) == ""


def test_batch_demand_import_row_status_precedence() -> None:
    assert decide_row_status("no project", "not_found", ["no item"], ["refused"]) == (
        "unresolved_reference",
        ["no project", "no item"],
    )
    assert decide_row_status(None, "ambiguous", ["two items"], ["refused"]) == (
        "ambiguous",
        ["two items", "refused"],
    )
    assert decide_row_status(None, "matched", [], ["refused"]) == ("invalid", ["refused"])
    assert decide_row_status(None, "matched", [], []) == ("matched", [])


class _ItemInactiveError(Exception):
    pass


def _refuse(item: str) -> None:
    raise _ItemInactiveError(f"{item} is archived.")


def test_batch_demand_import_refusals_name_the_inactive_item() -> None:
    refusals = new_demand_refusals(
        None, "Widget", assert_item_demandable=_refuse, item_error=_ItemInactiveError
    )
    assert refusals == ["Widget is archived."]
    assert (
        new_demand_refusals(
            None, None, assert_item_demandable=_refuse, item_error=_ItemInactiveError
        )
        == []
    )


class _Projects:
    def __init__(self, project: Any) -> None:
        self._project = project
        self.locked: list[list[int]] = []

    async def lock_for_share(self, ids: list[int]) -> None:
        self.locked.append(ids)

    async def get_by_id(self, project_id: int) -> Any:
        return self._project


async def test_batch_demand_import_locks_each_project_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(batch_demand_import, "assert_project_active", lambda project: None)
    project = SimpleNamespace(id=5)
    repo = _Projects(project)
    locked = LockedProjects(repo)  # type: ignore[arg-type]

    assert await locked.get(5) is project
    assert await locked.get(5) is project
    assert repo.locked == [[5]]


async def test_batch_demand_import_refuses_a_project_deleted_meanwhile() -> None:
    with pytest.raises(ProjectNotFoundError, match=r"Project #9 not found\."):
        await LockedProjects(_Projects(None)).get(9)  # type: ignore[arg-type]
