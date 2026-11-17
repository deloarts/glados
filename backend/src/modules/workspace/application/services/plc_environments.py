"""
The PLC environment of a product: the one it chose, or the default. A
product's choice must exist, and a newly chosen one must not be archived;
a product keeps an environment that was archived after it was chosen, so
it never has to be changed on the spot.
"""

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.workspace.domain.entities.plc_environment import PlcEnvironment
from src.modules.workspace.domain.entities.product import Product
from src.modules.workspace.domain.errors import PlcEnvironmentInvalidError
from src.modules.workspace.domain.errors import PlcEnvironmentNotFoundError
from src.modules.workspace.ports.outbound.repositories.plc_environment_repository import (
    IPlcEnvironmentRepository,
)


async def assert_usable(
    repo: IPlcEnvironmentRepository | None, environment_id: int | None, current_id: int | None
) -> None:
    if environment_id is None or environment_id == current_id:
        return
    if repo is None:
        raise PlcEnvironmentNotFoundError(f"PLC environment #{environment_id} not found.")
    environment = found_or_raise(
        await repo.get_by_id(environment_id),
        PlcEnvironmentNotFoundError,
        f"PLC environment #{environment_id} not found.",
    )
    if environment.archived:
        raise PlcEnvironmentInvalidError(
            f"PLC environment #{environment_id} ({environment.name!r}) is archived."
        )


async def environment_of(
    repo: IPlcEnvironmentRepository | None, product: Product
) -> PlcEnvironment | None:
    """The product's environment, or the default one; None without any."""
    if repo is None:
        return None
    if product.plc_environment_id is not None:
        chosen = await repo.get_by_id(product.plc_environment_id)
        if chosen is not None:
            return chosen
    return await repo.get_default()
