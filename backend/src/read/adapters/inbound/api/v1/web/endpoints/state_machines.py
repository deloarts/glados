"""
Read-only catalogue of every lifecycle: each machine's states, the rows of
its derivation table and the actions of its intent table, built live from
the tables the code runs on every request (see
src/read/domain/services/state_machine_catalog.py). Any authenticated user may
call it, like the other bootstrap-style endpoints under host.py: nothing
returned here is sensitive, and the handbook renders it.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User
from src.read.adapters.inbound.api.deps import get_state_machine_catalog_use_case
from src.read.application.dto.state_machine_dto import StateMachineCatalogDTO
from src.read.application.use_cases.state_machine.get_state_machine_catalog import (
    GetStateMachineCatalog,
)

router = APIRouter()


@router.get("/", response_model=StateMachineCatalogDTO)
async def get_state_machines(
    _: User = Depends(get_current_active_user),
    use_case: GetStateMachineCatalog = Depends(get_state_machine_catalog_use_case),
) -> StateMachineCatalogDTO:
    return await use_case.execute()
