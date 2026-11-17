"""
PAT surface, the EPLAN Data Portal for the SolidWorks add-in: whether the
portal is switched on, the parts an order code names exactly, the ranked
search and a part's picture. All of them only read; the add-in writes what
it takes from a part into the SolidWorks file, and PDM ingest brings it to
the catalogue (docs/EPLAN_DATA_PORTAL_INTEGRATION.md). The match, the
search and the picture need use:data_portal, the same as the web's search
in the create dialog, since they spend the organisation's portal token. The
status needs only a valid token.
"""

from fastapi import Depends
from fastapi import Query
from fastapi import Response
from fastapi.routing import APIRouter

from src.modules.external_data.adapters.inbound.api.deps.items import get_edp_availability_use_case
from src.modules.external_data.adapters.inbound.api.deps.items import get_edp_part_picture_use_case
from src.modules.external_data.adapters.inbound.api.deps.items import get_match_edp_parts_use_case
from src.modules.external_data.adapters.inbound.api.deps.items import get_search_edp_parts_use_case
from src.modules.external_data.adapters.inbound.api.schemas.bought_item_edp_schema import (
    EdpAvailabilityResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.bought_item_edp_schema import (
    EdpSearchResponse,
)
from src.modules.external_data.application.dto.bought_item_edp_dto import EdpAvailabilityResult
from src.modules.external_data.application.dto.bought_item_edp_dto import EdpSearchResult
from src.modules.external_data.application.use_cases.eplan_data_portal.edp_lookup import (
    GetEdpAvailability,
)
from src.modules.external_data.application.use_cases.eplan_data_portal.edp_lookup import (
    GetEdpPartPicture,
)
from src.modules.external_data.application.use_cases.eplan_data_portal.edp_lookup import (
    MatchEdpParts,
)
from src.modules.external_data.application.use_cases.eplan_data_portal.edp_lookup import (
    SearchEdpParts,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/status", response_model=EdpAvailabilityResponse)
async def read_edp_status(
    _: User = Depends(get_current_user_pat),
    use_case: GetEdpAvailability = Depends(get_edp_availability_use_case),
) -> EdpAvailabilityResult:
    """Whether the Data Portal is switched on."""
    return await use_case.execute()


@router.get("/match", response_model=EdpSearchResponse)
async def match_edp_parts(
    number: str = Query(..., min_length=2, max_length=100),
    manufacturer_id: int | None = Query(default=None),
    actor: User = Depends(get_current_user_pat),
    use_case: MatchEdpParts = Depends(get_match_edp_parts_use_case),
) -> EdpSearchResult:
    """The parts an order, type or EPLAN part number names exactly, each
    with the values it fills and the item that already has it. A given
    manufacturer narrows several hits to its own parts."""
    return await use_case.execute(actor=actor, number=number, manufacturer_id=manufacturer_id)


@router.get("/search", response_model=EdpSearchResponse)
async def search_edp_parts(
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(default=10, ge=1, le=20),
    actor: User = Depends(get_current_user_pat),
    use_case: SearchEdpParts = Depends(get_search_edp_parts_use_case),
) -> EdpSearchResult:
    """Ranked Data Portal hits for a number or a name, shaped like /match."""
    return await use_case.execute(actor=actor, query=q, limit=limit)


@router.get(
    "/parts/{part_id}/picture",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
async def get_edp_part_picture(
    part_id: int,
    actor: User = Depends(get_current_user_pat),
    use_case: GetEdpPartPicture = Depends(get_edp_part_picture_use_case),
) -> Response:
    """The part's product picture, passed through Glados."""
    picture = await use_case.execute(actor=actor, part_id=part_id)
    return Response(
        content=picture,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600"},
    )
