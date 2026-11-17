"""
Moves the default for assemblies off its current holder. Create and update
call it before saving the newly flagged method, so the single-default index
never sees two flagged rows within one transaction.
"""

from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    IFabricationMethodRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


async def clear_assembly_default(
    fabrication_method_repo: IFabricationMethodRepository, actor: User, *, keep_id: int
) -> None:
    """Clears the flag on the current holder unless it is `keep_id`, the
    method about to carry it (0 for one still being created)."""
    holder = await fabrication_method_repo.get_default_for_assemblies()
    if holder is None or holder.id == keep_id:
        return
    holder.default_for_assemblies = False
    holder.changed = now_utc()
    holder.changes = append_changelog(
        holder.changes, actor.full_name, "No longer the default for assemblies."
    )
    await fabrication_method_repo.save(holder)
    log.info(
        f"Fabrication method {holder.name!r}, ID={holder.id}, is no longer the default "
        "for assemblies."
    )
