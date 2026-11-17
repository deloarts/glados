"""
PAT surface, backend version.

Lets an external client such as the SolidWorks add-in ask which backend
version it talks to and which `pat` contract minor that version serves, so
it can refuse a minor it was not built for before it calls anything else.
Any valid PAT may call it; it needs no permission because a version number
reveals nothing about the data.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.adapters.inbound.api.schemas.version_schema import PatVersionResponse
from src.modules.platform.const import PAT_CONTRACT
from src.modules.platform.const import VERSION
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/version", response_model=PatVersionResponse)
async def read_version(_: User = Depends(get_current_user_pat)) -> PatVersionResponse:
    """Return the backend version and the `pat` contract minor it serves."""
    return PatVersionResponse(version=VERSION, pat_contract=PAT_CONTRACT)
