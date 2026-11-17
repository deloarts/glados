"""
PAT surface: bootstraps the add-in's offline lookup cache from one call
(suppliers, article_groups, fabrication_methods, inspection_methods,
source_item_types, source_items) instead of six capped list requests,
with weak-ETag revalidation so a repeat call with an unchanged cache costs
six cheap aggregate queries instead of six full list scans.
"""

from fastapi import Depends
from fastapi import Header
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.responses import Response
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.lookups import get_lookups_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.lookups_schema import LookupsResponse
from src.modules.catalogue.application.use_cases.lookups.get_lookups import GetLookups
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_user_pat
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.label_languages import label_languages

router = APIRouter()


def _if_none_match_matches(header_value: str | None, etag: str) -> bool:
    """Weak comparison of an If-None-Match header against the current opaque tag.

    The header may carry a comma separated list, each entry optionally weak
    (W/ prefix) and quoted, or the single wildcard "*" that matches any
    current representation.
    """
    if header_value is None:
        return False
    for candidate in header_value.split(","):
        candidate = candidate.strip()
        if candidate == "*":
            return True
        if candidate.startswith("W/"):
            candidate = candidate[2:]
        if candidate.strip('"') == etag:
            return True
    return False


@router.get(
    "/",
    response_model=None,
    responses={
        200: {"model": LookupsResponse},
        304: {"description": "The cache identified by If-None-Match is still current."},
    },
)
async def read_lookups(
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    _: User = Depends(get_current_user_pat),
    use_case: GetLookups = Depends(get_lookups_use_case),
) -> Response:
    etag = await use_case.compute_etag(label_languages())
    weak_etag = f'W/"{etag}"'
    headers = {"ETag": weak_etag, "Cache-Control": "private, no-cache"}

    if _if_none_match_matches(if_none_match, etag):
        return Response(status_code=304, headers=headers)

    result = await use_case.execute()
    payload = LookupsResponse.model_validate(result.model_dump())
    return JSONResponse(content=jsonable_encoder(payload), headers=headers)
