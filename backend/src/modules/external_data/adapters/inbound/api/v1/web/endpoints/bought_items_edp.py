"""
The EPLAN Data Portal on single bought items: the search behind the create
dialog, and the lookup on an existing item with the apply action. The
search and the part picture need use:data_portal, the lookup and apply the
bought item write permission.
"""

from fastapi import Depends
from fastapi import Query
from fastapi import Response
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_schema import (
    BoughtItemWebResponse,
)
from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.external_data.adapters.inbound.api.deps.items import get_apply_edp_lookup_use_case
from src.modules.external_data.adapters.inbound.api.deps.items import get_edp_part_picture_use_case
from src.modules.external_data.adapters.inbound.api.deps.items import (
    get_lookup_bought_item_in_edp_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.items import get_search_edp_parts_use_case
from src.modules.external_data.adapters.inbound.api.schemas.bought_item_edp_schema import (
    ApplyEdpLookupRequest,
)
from src.modules.external_data.adapters.inbound.api.schemas.bought_item_edp_schema import (
    EdpItemLookupResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.bought_item_edp_schema import (
    EdpSearchResponse,
)
from src.modules.external_data.application.dto.bought_item_edp_dto import ApplyEdpLookupCommand
from src.modules.external_data.application.dto.bought_item_edp_dto import EdpItemLookupResult
from src.modules.external_data.application.dto.bought_item_edp_dto import EdpSearchResult
from src.modules.external_data.application.use_cases.eplan_data_portal.edp_lookup import (
    ApplyEdpLookup,
)
from src.modules.external_data.application.use_cases.eplan_data_portal.edp_lookup import (
    GetEdpPartPicture,
)
from src.modules.external_data.application.use_cases.eplan_data_portal.edp_lookup import (
    LookupBoughtItemInEdp,
)
from src.modules.external_data.application.use_cases.eplan_data_portal.edp_lookup import (
    SearchEdpParts,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/search", response_model=EdpSearchResponse)
async def search_edp_parts(
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(default=10, ge=1, le=20),
    actor: User = Depends(get_current_active_user),
    use_case: SearchEdpParts = Depends(get_search_edp_parts_use_case),
) -> EdpSearchResult:
    """Ranked Data Portal hits for an order, type or EPLAN part number or a
    name, each with the values it fills and the item that already has it."""
    return await use_case.execute(actor=actor, query=q, limit=limit)


@router.get(
    "/parts/{part_id}/picture",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
async def get_edp_part_picture(
    part_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetEdpPartPicture = Depends(get_edp_part_picture_use_case),
) -> Response:
    """The part's product picture, served from Glados' own origin."""
    picture = await use_case.execute(actor=actor, part_id=part_id)
    return Response(
        content=picture,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/items/{item_id}/lookup", response_model=EdpItemLookupResponse)
async def lookup_bought_item_in_edp(
    item_id: int,
    part_id: int | None = Query(default=None),
    actor: User = Depends(get_current_active_user),
    use_case: LookupBoughtItemInEdp = Depends(get_lookup_bought_item_in_edp_use_case),
) -> EdpItemLookupResult:
    """Compares the item with its Data Portal part: the linked one, the
    given part_id, or the part its order code finds."""
    return await use_case.execute(actor=actor, item_id=item_id, part_id=part_id)


@router.post("/items/{item_id}/apply", response_model=BoughtItemWebResponse)
async def apply_edp_lookup(
    item_id: int,
    body: ApplyEdpLookupRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ApplyEdpLookup = Depends(get_apply_edp_lookup_use_case),
) -> BoughtItemResult:
    """Takes the chosen fields from the Data Portal part through the normal
    item update, then links the item to the part and requests its picture."""
    cmd = ApplyEdpLookupCommand(**body.model_dump())
    return await use_case.execute(actor=actor, item_id=item_id, cmd=cmd)
