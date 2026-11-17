"""
The dependencies of Quality & documents' routes whose implementations live
in the read tier, which the composition root binds at startup
(`src/bootstrap/bindings.py`).
"""

from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.inbound.api.deps.binding import Binding
from src.modules.platform.adapters.inbound.api.deps.database import get_db
from src.modules.quality.application.services.print_roots import IPrintRootResolver

print_root_resolver: Binding[Callable[[AsyncSession], IPrintRootResolver]] = Binding(
    "The print root resolver"
)


def get_print_root_resolver(
    db: AsyncSession = Depends(get_db, scope="function"),
) -> IPrintRootResolver:
    return print_root_resolver.get()(db)
