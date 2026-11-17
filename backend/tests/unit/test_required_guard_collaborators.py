"""
A collaborator a guard reads from is required, so a use case built without
it fails at construction instead of skipping the guard in silence. The
allocation writers need both families' allocations to refuse taking pieces
that already arrived for another demand, auto-allocate needs the projects to
skip deleted ones, a piece disposition needs the lot creation for its rework
and replacement lots and the made demand repositories to move the lot's
coverage, a disposition of rejected pieces at a completion every repository
it writes, the raw material settlement of a lot it empties included, a
completion or scrap the settings whose tenant timezone gives its day, and a
force-complete needs the raw material repositories to settle
the lot's input demand. A delivery needs the lots to check a MADE line's
booking against its lot, and every repository the disposition of lost pieces
and the refit of a lost or short line's allocations write.
"""

import inspect
from collections.abc import Callable
from typing import Any

import pytest

from src.modules.fulfillment.application.services.piece_disposition import apply_disposition
from src.modules.fulfillment.application.services.piece_disposition import reallocate_lot_coverage
from src.modules.fulfillment.application.use_cases._demand_family.allocation_writers import (
    OrderLineAllocationWriter,
)
from src.modules.fulfillment.application.use_cases._demand_family.auto_allocate import (
    AutoAllocateOnOrderLines,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.auto_allocate import (
    AutoAllocate,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    CreateAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    DeleteAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    UpdateAllocation,
)
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    ProcessOrderItemDelivery,
)
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CompleteLot
from src.modules.fulfillment.application.use_cases.production_order.record_production_order_completion import (
    RecordProductionOrderCompletion,
)
from src.modules.fulfillment.application.use_cases.production_order.scrap_production_pieces import (
    ScrapProductionPieces,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.auto_allocate import (
    AutoAllocateSourceItemDemand,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    CreateSourceItemAllocation,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    DeleteSourceItemAllocation,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    UpdateSourceItemAllocation,
)

_DISPOSITION = ("create_lot", "made_item_demand_repo", "made_item_allocation_repo")
_SETTLEMENT = ("source_item_demand_repo", "source_item_allocation_repo")

REQUIRED: list[tuple[Callable[..., Any], tuple[str, ...]]] = [
    (OrderLineAllocationWriter.__init__, ("fill_repos",)),
    (CreateAllocation.__init__, ("fill_repos",)),
    (UpdateAllocation.__init__, ("fill_repos",)),
    (DeleteAllocation.__init__, ("fill_repos",)),
    (CreateSourceItemAllocation.__init__, ("fill_repos",)),
    (UpdateSourceItemAllocation.__init__, ("fill_repos",)),
    (DeleteSourceItemAllocation.__init__, ("fill_repos",)),
    (AutoAllocateOnOrderLines.__init__, ("fill_repos", "project_repo")),
    (AutoAllocate.__init__, ("fill_repos", "project_repo")),
    (AutoAllocateSourceItemDemand.__init__, ("fill_repos", "project_repo")),
    (apply_disposition, _DISPOSITION),
    (reallocate_lot_coverage, _DISPOSITION[1:]),
    (ScrapProductionPieces.__init__, (*_DISPOSITION, "bought_allocation_repo", "settings_repo")),
    (
        RecordProductionOrderCompletion.__init__,
        (
            *_DISPOSITION,
            *_SETTLEMENT,
            "order_item_repo",
            "parent_order_repo",
            "interruption_repo",
            "bought_allocation_repo",
            "settings_repo",
        ),
    ),
    (
        ProcessOrderItemDelivery.__init__,
        (
            *_DISPOSITION,
            *_SETTLEMENT,
            "lot_repo",
            "production_order_repo",
            "interruption_repo",
            "bought_item_allocation_repo",
        ),
    ),
    (CompleteLot.__init__, (*_SETTLEMENT, "bought_allocation_repo")),
]


@pytest.mark.parametrize(
    ("target", "names"),
    REQUIRED,
    ids=[f"{t.__qualname__}" for t, _ in REQUIRED],
)
def test_a_guard_collaborator_has_no_default_and_is_not_optional(
    target: Callable[..., Any], names: tuple[str, ...]
) -> None:
    parameters = inspect.signature(target).parameters
    for name in names:
        if name not in parameters:
            # A subclass that forwards **kwargs inherits the base's rule.
            continue
        parameter = parameters[name]
        assert parameter.default is inspect.Parameter.empty, f"{name} has a default"
        assert "None" not in str(parameter.annotation), f"{name} is optional"
