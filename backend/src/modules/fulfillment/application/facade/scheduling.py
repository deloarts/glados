"""
The schedule queries other modules run: the working calendars of machines,
the target dates of lots and the explanations of production orders' earliest
starts, and the repository ports these queries read, which callers pass in.
"""

from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.services.scheduling_context import TargetDateSource
from src.modules.fulfillment.application.services.scheduling_context import build_machine_calendars
from src.modules.fulfillment.application.services.scheduling_context import (
    compute_schedule_explanations_for_orders,
)
from src.modules.fulfillment.application.services.scheduling_context import (
    describe_lot_target_dates,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_calendar_repository import (
    IMachineCalendarRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    IMachinePoolRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    IProductionMachineRepository,
)

__all__ = [
    "IMachineCalendarRepository",
    "IMachinePoolRepository",
    "IProductionMachineRepository",
    "SchedulingRepos",
    "TargetDateSource",
    "build_machine_calendars",
    "compute_schedule_explanations_for_orders",
    "describe_lot_target_dates",
]
