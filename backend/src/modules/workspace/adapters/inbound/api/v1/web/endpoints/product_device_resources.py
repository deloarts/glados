"""
Endpoints for the hand-maintained lists product devices pick from: the
plain option lists (driving media, component roles, energy behaviours) and
the device kinds with their positions and parameters. The lists are short
and returned whole. Entries are archived, never deleted, and moved up or
down by hand, since pickers offer them in this order.
"""

from fastapi import Depends
from fastapi import Query
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.list_move_schema import ListMoveRequest
from src.modules.platform.adapters.inbound.api.schemas.list_move_schema import ListPlaceRequest
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_create_product_device_kind_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_create_product_device_option_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_move_product_device_kind_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_move_product_device_option_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_place_product_device_kind_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_place_product_device_option_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_product_device_kinds_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_product_device_options_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_set_product_device_kind_archived_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_set_product_device_option_archived_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_update_product_device_kind_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.product_devices import (
    get_update_product_device_option_use_case,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_device_schema import (
    ProductDeviceKindResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_device_schema import (
    ProductDeviceKindSaveRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_device_schema import (
    ProductDeviceOptionCreateRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_device_schema import (
    ProductDeviceOptionResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.product_device_schema import (
    ProductDeviceOptionUpdateRequest,
)
from src.modules.workspace.application.dto.product_device_resource_dto import (
    CreateProductDeviceOptionCommand,
)
from src.modules.workspace.application.dto.product_device_resource_dto import (
    SaveProductDeviceKindCommand,
)
from src.modules.workspace.application.dto.product_device_resource_dto import (
    UpdateProductDeviceOptionCommand,
)
from src.modules.workspace.application.use_cases.product_device_resource.kinds import (
    CreateProductDeviceKind,
)
from src.modules.workspace.application.use_cases.product_device_resource.kinds import (
    GetProductDeviceKinds,
)
from src.modules.workspace.application.use_cases.product_device_resource.kinds import (
    MoveProductDeviceKind,
)
from src.modules.workspace.application.use_cases.product_device_resource.kinds import (
    PlaceProductDeviceKind,
)
from src.modules.workspace.application.use_cases.product_device_resource.kinds import (
    SetProductDeviceKindArchived,
)
from src.modules.workspace.application.use_cases.product_device_resource.kinds import (
    UpdateProductDeviceKind,
)
from src.modules.workspace.application.use_cases.product_device_resource.options import (
    CreateProductDeviceOption,
)
from src.modules.workspace.application.use_cases.product_device_resource.options import (
    GetProductDeviceOptions,
)
from src.modules.workspace.application.use_cases.product_device_resource.options import (
    MoveProductDeviceOption,
)
from src.modules.workspace.application.use_cases.product_device_resource.options import (
    PlaceProductDeviceOption,
)
from src.modules.workspace.application.use_cases.product_device_resource.options import (
    SetProductDeviceOptionArchived,
)
from src.modules.workspace.application.use_cases.product_device_resource.options import (
    UpdateProductDeviceOption,
)
from src.modules.workspace.domain.value_objects.product_device_option_category import (
    ProductDeviceOptionCategory,
)

router = APIRouter()

# ── Options ───────────────────────────────────────────────────────────


@router.get("/options", response_model=list[ProductDeviceOptionResponse])
async def read_product_device_options(
    category: ProductDeviceOptionCategory | None = Query(default=None),
    include_archived: bool = Query(default=False),
    _: User = Depends(get_current_active_user),
    use_case: GetProductDeviceOptions = Depends(get_product_device_options_use_case),
) -> list[ProductDeviceOptionResponse]:
    results = await use_case.execute(category, include_archived)
    return [ProductDeviceOptionResponse.model_validate(r.model_dump()) for r in results]


@router.post(
    "/options", response_model=ProductDeviceOptionResponse, status_code=status.HTTP_201_CREATED
)
async def create_product_device_option(
    body: ProductDeviceOptionCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateProductDeviceOption = Depends(get_create_product_device_option_use_case),
) -> ProductDeviceOptionResponse:
    result = await use_case.execute(actor, CreateProductDeviceOptionCommand(**body.model_dump()))
    return ProductDeviceOptionResponse.model_validate(result.model_dump())


@router.put("/options/{option_id}", response_model=ProductDeviceOptionResponse)
async def update_product_device_option(
    option_id: int,
    body: ProductDeviceOptionUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateProductDeviceOption = Depends(get_update_product_device_option_use_case),
) -> ProductDeviceOptionResponse:
    result = await use_case.execute(
        actor, option_id, UpdateProductDeviceOptionCommand(**body.model_dump())
    )
    return ProductDeviceOptionResponse.model_validate(result.model_dump())


@router.post("/options/{option_id}/archive", response_model=ProductDeviceOptionResponse)
async def archive_product_device_option(
    option_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: SetProductDeviceOptionArchived = Depends(
        get_set_product_device_option_archived_use_case
    ),
) -> ProductDeviceOptionResponse:
    result = await use_case.execute(actor, option_id, archived=True)
    return ProductDeviceOptionResponse.model_validate(result.model_dump())


@router.post("/options/{option_id}/restore", response_model=ProductDeviceOptionResponse)
async def restore_product_device_option(
    option_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: SetProductDeviceOptionArchived = Depends(
        get_set_product_device_option_archived_use_case
    ),
) -> ProductDeviceOptionResponse:
    result = await use_case.execute(actor, option_id, archived=False)
    return ProductDeviceOptionResponse.model_validate(result.model_dump())


@router.post("/options/{option_id}/move", response_model=list[ProductDeviceOptionResponse])
async def move_product_device_option(
    option_id: int,
    body: ListMoveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: MoveProductDeviceOption = Depends(get_move_product_device_option_use_case),
) -> list[ProductDeviceOptionResponse]:
    results = await use_case.execute(actor, option_id, body.direction)
    return [ProductDeviceOptionResponse.model_validate(r.model_dump()) for r in results]


@router.post("/options/{option_id}/place", response_model=list[ProductDeviceOptionResponse])
async def place_product_device_option(
    option_id: int,
    body: ListPlaceRequest,
    actor: User = Depends(get_current_active_user),
    use_case: PlaceProductDeviceOption = Depends(get_place_product_device_option_use_case),
) -> list[ProductDeviceOptionResponse]:
    """Puts the entry next to another one of its category, as dragging its row does."""
    results = await use_case.execute(
        actor, option_id, after_id=body.after_id, before_id=body.before_id
    )
    return [ProductDeviceOptionResponse.model_validate(r.model_dump()) for r in results]


# ── Kinds ─────────────────────────────────────────────────────────────


@router.get("/kinds", response_model=list[ProductDeviceKindResponse])
async def read_product_device_kinds(
    include_archived: bool = Query(default=False),
    _: User = Depends(get_current_active_user),
    use_case: GetProductDeviceKinds = Depends(get_product_device_kinds_use_case),
) -> list[ProductDeviceKindResponse]:
    results = await use_case.execute(include_archived)
    return [ProductDeviceKindResponse.model_validate(r.model_dump()) for r in results]


@router.post(
    "/kinds", response_model=ProductDeviceKindResponse, status_code=status.HTTP_201_CREATED
)
async def create_product_device_kind(
    body: ProductDeviceKindSaveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateProductDeviceKind = Depends(get_create_product_device_kind_use_case),
) -> ProductDeviceKindResponse:
    result = await use_case.execute(actor, SaveProductDeviceKindCommand(**body.model_dump()))
    return ProductDeviceKindResponse.model_validate(result.model_dump())


@router.put("/kinds/{kind_id}", response_model=ProductDeviceKindResponse)
async def update_product_device_kind(
    kind_id: int,
    body: ProductDeviceKindSaveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateProductDeviceKind = Depends(get_update_product_device_kind_use_case),
) -> ProductDeviceKindResponse:
    result = await use_case.execute(
        actor, kind_id, SaveProductDeviceKindCommand(**body.model_dump())
    )
    return ProductDeviceKindResponse.model_validate(result.model_dump())


@router.post("/kinds/{kind_id}/archive", response_model=ProductDeviceKindResponse)
async def archive_product_device_kind(
    kind_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: SetProductDeviceKindArchived = Depends(get_set_product_device_kind_archived_use_case),
) -> ProductDeviceKindResponse:
    result = await use_case.execute(actor, kind_id, archived=True)
    return ProductDeviceKindResponse.model_validate(result.model_dump())


@router.post("/kinds/{kind_id}/restore", response_model=ProductDeviceKindResponse)
async def restore_product_device_kind(
    kind_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: SetProductDeviceKindArchived = Depends(get_set_product_device_kind_archived_use_case),
) -> ProductDeviceKindResponse:
    result = await use_case.execute(actor, kind_id, archived=False)
    return ProductDeviceKindResponse.model_validate(result.model_dump())


@router.post("/kinds/{kind_id}/move", response_model=list[ProductDeviceKindResponse])
async def move_product_device_kind(
    kind_id: int,
    body: ListMoveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: MoveProductDeviceKind = Depends(get_move_product_device_kind_use_case),
) -> list[ProductDeviceKindResponse]:
    results = await use_case.execute(actor, kind_id, body.direction)
    return [ProductDeviceKindResponse.model_validate(r.model_dump()) for r in results]


@router.post("/kinds/{kind_id}/place", response_model=list[ProductDeviceKindResponse])
async def place_product_device_kind(
    kind_id: int,
    body: ListPlaceRequest,
    actor: User = Depends(get_current_active_user),
    use_case: PlaceProductDeviceKind = Depends(get_place_product_device_kind_use_case),
) -> list[ProductDeviceKindResponse]:
    """Puts the kind next to another one, as dragging its row does."""
    results = await use_case.execute(
        actor, kind_id, after_id=body.after_id, before_id=body.before_id
    )
    return [ProductDeviceKindResponse.model_validate(r.model_dump()) for r in results]
