"""
Whether Planning & fulfillment uses an inspection method as the default for
production steps that require QA, so archiving it is refused. Planning &
fulfillment's settings store answers this port as it is: its production
section names the default inspection method.
"""

from typing import Protocol


class ProductionQaDefault(Protocol):
    @property
    def default_inspection_method_id(self) -> int | None: ...


class IInspectionMethodUsage(Protocol):
    async def get_production(self) -> ProductionQaDefault:
        """The production settings, which name the default inspection
        method of steps that require QA."""
        ...
