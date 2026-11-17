"""
Global search across the resources in SEARCH_RESOURCES order. Open
to any active user, same as every one of those resources' own list
endpoints, plus the contacts for a user who may read them.
"""

from fastapi import Depends
from fastapi import Query
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User
from src.read.adapters.inbound.api.deps import get_global_search_use_case
from src.read.application.dto.search_dto import GlobalSearchResult
from src.read.application.use_cases.search.global_search import GlobalSearch

router = APIRouter()


@router.get("/", response_model=GlobalSearchResult)
async def search(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=5, ge=1, le=20),
    actor: User = Depends(get_current_active_user),
    use_case: GlobalSearch = Depends(get_global_search_use_case),
) -> GlobalSearchResult:
    return await use_case.execute(query=q, limit=limit, actor=actor)
