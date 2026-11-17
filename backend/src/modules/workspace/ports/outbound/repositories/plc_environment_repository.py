"""
Repository interface for PLC environments.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.workspace.domain.entities.plc_environment import PlcEnvironment


@runtime_checkable
class IPlcEnvironmentRepository(Protocol):
    async def get_by_id(self, id: int) -> PlcEnvironment | None: ...

    async def get_many(self, include_archived: bool) -> list[PlcEnvironment]:
        """Ordered by name."""
        ...

    async def get_live_by_name(self, name: str) -> PlcEnvironment | None:
        """The live environment of this name, compared case-insensitively."""
        ...

    async def get_default(self) -> PlcEnvironment | None: ...

    async def save(self, environment: PlcEnvironment) -> PlcEnvironment:
        """Insert (id == 0) or update (id > 0)."""
        ...

    async def clear_default_except(self, id: int) -> None:
        """Takes the default mark from every environment but this one."""
        ...
