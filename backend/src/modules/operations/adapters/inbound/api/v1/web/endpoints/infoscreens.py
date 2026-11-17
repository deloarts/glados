"""
Infoscreen endpoints. Prefix `/infoscreens`. Reading the screens and the
preview feed is open to every signed-in user, and so is reading the default
display schedule; creating, editing, archiving and restoring need
write:infoscreens, checked in the use case, and so do setting the default
display schedule and the place search of the weather widget's location
picker. There is no
DELETE route, as for all master data.
"""

from fastapi import Depends
from fastapi import Query
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_create_infoscreen_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_display_schedule_default_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import get_infoscreen_feed_use_case
from src.modules.operations.adapters.inbound.api.deps.terminals import get_infoscreen_use_case
from src.modules.operations.adapters.inbound.api.deps.terminals import get_infoscreens_use_case
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_search_weather_places_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_set_display_schedule_default_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_set_infoscreen_archived_use_case,
)
from src.modules.operations.adapters.inbound.api.deps.terminals import (
    get_update_infoscreen_use_case,
)
from src.modules.operations.adapters.inbound.api.schemas.infoscreen_schema import (
    DisplayScheduleDefaultRequest,
)
from src.modules.operations.adapters.inbound.api.schemas.infoscreen_schema import (
    DisplayScheduleDefaultResponse,
)
from src.modules.operations.adapters.inbound.api.schemas.infoscreen_schema import (
    InfoscreenCreateRequest,
)
from src.modules.operations.adapters.inbound.api.schemas.infoscreen_schema import (
    InfoscreenFeedResponse,
)
from src.modules.operations.adapters.inbound.api.schemas.infoscreen_schema import InfoscreenResponse
from src.modules.operations.adapters.inbound.api.schemas.infoscreen_schema import (
    InfoscreenUpdateRequest,
)
from src.modules.operations.adapters.inbound.api.schemas.infoscreen_schema import (
    WeatherPlaceResponse,
)
from src.modules.operations.application.dto.infoscreen_dto import CreateInfoscreenCommand
from src.modules.operations.application.dto.infoscreen_dto import DisplayScheduleDefaultResult
from src.modules.operations.application.dto.infoscreen_dto import InfoscreenResult
from src.modules.operations.application.dto.infoscreen_dto import SetDisplayScheduleDefaultCommand
from src.modules.operations.application.dto.infoscreen_dto import UpdateInfoscreenCommand
from src.modules.operations.application.dto.infoscreen_dto import WeatherPlaceResult
from src.modules.operations.application.dto.infoscreen_feed_dto import InfoscreenFeedResult
from src.modules.operations.application.use_cases.infoscreen.display_schedule_default import (
    GetDisplayScheduleDefault,
)
from src.modules.operations.application.use_cases.infoscreen.display_schedule_default import (
    SetDisplayScheduleDefault,
)
from src.modules.operations.application.use_cases.infoscreen.get_infoscreen_feed import (
    GetInfoscreenFeed,
)
from src.modules.operations.application.use_cases.infoscreen.infoscreen_crud import CreateInfoscreen
from src.modules.operations.application.use_cases.infoscreen.infoscreen_crud import GetInfoscreen
from src.modules.operations.application.use_cases.infoscreen.infoscreen_crud import GetInfoscreens
from src.modules.operations.application.use_cases.infoscreen.infoscreen_crud import (
    SetInfoscreenArchived,
)
from src.modules.operations.application.use_cases.infoscreen.infoscreen_crud import UpdateInfoscreen
from src.modules.operations.application.use_cases.infoscreen.search_weather_places import (
    SearchWeatherPlaces,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.language import Language

router = APIRouter()


@router.get("/", response_model=list[InfoscreenResponse])
async def read_infoscreens(
    include_archived: bool = Query(default=False),
    _: User = Depends(get_current_active_user),
    use_case: GetInfoscreens = Depends(get_infoscreens_use_case),
) -> list[InfoscreenResult]:
    return await use_case.execute(include_archived=include_archived)


@router.post("/", response_model=InfoscreenResponse, status_code=status.HTTP_201_CREATED)
async def create_infoscreen(
    body: InfoscreenCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateInfoscreen = Depends(get_create_infoscreen_use_case),
) -> InfoscreenResult:
    return await use_case.execute(actor, CreateInfoscreenCommand(**body.model_dump()))


@router.get("/weather-places", response_model=list[WeatherPlaceResponse])
async def search_weather_places(
    q: str = Query(..., min_length=2, max_length=100),
    country: str = Query(..., min_length=2, max_length=2, pattern="^[A-Za-z]{2}$"),
    language: Language | None = Query(default=None),
    actor: User = Depends(get_current_active_user),
    use_case: SearchWeatherPlaces = Depends(get_search_weather_places_use_case),
) -> list[WeatherPlaceResult]:
    """Towns named like `q` in the country with ISO code `country`, for the
    weather widget's location picker. Needs write:infoscreens; 503 when the
    weather is switched off or the weather service does not answer."""
    return await use_case.execute(actor, q, country, language)


@router.get("/display-schedule-default", response_model=DisplayScheduleDefaultResponse)
async def read_display_schedule_default(
    _: User = Depends(get_current_active_user),
    use_case: GetDisplayScheduleDefault = Depends(get_display_schedule_default_use_case),
) -> DisplayScheduleDefaultResult:
    """The schedule the screens in the "default" mode follow."""
    return await use_case.execute()


@router.put("/display-schedule-default", response_model=DisplayScheduleDefaultResponse)
async def set_display_schedule_default(
    body: DisplayScheduleDefaultRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SetDisplayScheduleDefault = Depends(get_set_display_schedule_default_use_case),
) -> DisplayScheduleDefaultResult:
    """Sets the default schedule. Needs write:infoscreens."""
    return await use_case.execute(actor, SetDisplayScheduleDefaultCommand(**body.model_dump()))


@router.get("/{infoscreen_id}", response_model=InfoscreenResponse)
async def read_infoscreen(
    infoscreen_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetInfoscreen = Depends(get_infoscreen_use_case),
) -> InfoscreenResult:
    return await use_case.execute(infoscreen_id)


@router.patch("/{infoscreen_id}", response_model=InfoscreenResponse)
async def update_infoscreen(
    infoscreen_id: int,
    body: InfoscreenUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateInfoscreen = Depends(get_update_infoscreen_use_case),
) -> InfoscreenResult:
    cmd = UpdateInfoscreenCommand(**body.model_dump(), fields_set=set(body.model_fields_set))
    return await use_case.execute(actor, infoscreen_id, cmd)


@router.post("/{infoscreen_id}/archive", response_model=InfoscreenResponse)
async def archive_infoscreen(
    infoscreen_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: SetInfoscreenArchived = Depends(get_set_infoscreen_archived_use_case),
) -> InfoscreenResult:
    return await use_case.execute(actor, infoscreen_id, archived=True)


@router.post("/{infoscreen_id}/restore", response_model=InfoscreenResponse)
async def restore_infoscreen(
    infoscreen_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: SetInfoscreenArchived = Depends(get_set_infoscreen_archived_use_case),
) -> InfoscreenResult:
    return await use_case.execute(actor, infoscreen_id, archived=False)


@router.get("/{infoscreen_id}/feed", response_model=InfoscreenFeedResponse)
async def read_infoscreen_feed(
    infoscreen_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetInfoscreenFeed = Depends(get_infoscreen_feed_use_case),
) -> InfoscreenFeedResult:
    """The builder preview: the same feed a display of this screen gets."""
    return await use_case.execute(infoscreen_id)
