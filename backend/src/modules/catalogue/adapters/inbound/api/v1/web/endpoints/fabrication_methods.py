"""
Fabrication method endpoints, manages the catalogue of fabrication methods
referenced by made item processes.
"""

from datetime import tzinfo

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_archive_fabrication_method_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_assembly_default_fabrication_method_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_create_fabrication_method_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import get_fabrication_method_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import get_fabrication_methods_use_case
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_move_fabrication_method_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_place_fabrication_method_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_restore_fabrication_method_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.items import (
    get_update_fabrication_method_use_case,
)
from src.modules.catalogue.adapters.inbound.api.schemas.fabrication_method_schema import (
    FabricationMethodCreateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.fabrication_method_schema import (
    FabricationMethodFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.fabrication_method_schema import (
    FabricationMethodUpdateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.fabrication_method_schema import (
    FabricationMethodWebResponse,
)
from src.modules.catalogue.application.dto.fabrication_method_dto import (
    CreateFabricationMethodCommand,
)
from src.modules.catalogue.application.dto.fabrication_method_dto import (
    UpdateFabricationMethodCommand,
)
from src.modules.catalogue.application.use_cases.fabrication_method.archive_fabrication_method import (
    ArchiveFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.create_fabrication_method import (
    CreateFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.get_fabrication_method import (
    GetAssemblyDefaultFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.get_fabrication_method import (
    GetFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.get_fabrication_method import (
    GetFabricationMethods,
)
from src.modules.catalogue.application.use_cases.fabrication_method.move_fabrication_method import (
    MoveFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.move_fabrication_method import (
    PlaceFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.restore_fabrication_method import (
    RestoreFabricationMethod,
)
from src.modules.catalogue.application.use_cases.fabrication_method.update_fabrication_method import (
    UpdateFabricationMethod,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.misc import get_label_languages
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.schemas.list_move_schema import ListMoveRequest
from src.modules.platform.adapters.inbound.api.schemas.list_move_schema import ListPlaceRequest
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[FabricationMethodWebResponse])
async def read_fabrication_methods(
    params: FabricationMethodFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    zone: tzinfo = Depends(get_tenant_zone),
    languages: tuple[str, ...] = Depends(get_label_languages),
    use_case: GetFabricationMethods = Depends(get_fabrication_methods_use_case),
) -> PageResponse[FabricationMethodWebResponse]:
    result = await use_case.execute(params.to_dto(zone, languages))
    return PageResponse.from_result(result, params, item_model=FabricationMethodWebResponse)


@router.post("/", response_model=FabricationMethodWebResponse, status_code=status.HTTP_201_CREATED)
async def create_fabrication_method(
    body: FabricationMethodCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateFabricationMethod = Depends(get_create_fabrication_method_use_case),
) -> FabricationMethodWebResponse:
    cmd = CreateFabricationMethodCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, cmd=cmd)
    return FabricationMethodWebResponse.model_validate(result.model_dump())


# Declared before GET /{fabrication_method_id}, which would otherwise match
# "assembly-default" as an id and reject it with 422.
@router.get("/assembly-default", response_model=FabricationMethodWebResponse | None)
async def read_assembly_default_fabrication_method(
    _: User = Depends(get_current_active_user),
    use_case: GetAssemblyDefaultFabricationMethod = Depends(
        get_assembly_default_fabrication_method_use_case
    ),
) -> FabricationMethodWebResponse | None:
    """The method preselected for assemblies, or null when none is set."""
    result = await use_case.execute()
    return FabricationMethodWebResponse.model_validate(result.model_dump()) if result else None


@router.get("/{fabrication_method_id}", response_model=FabricationMethodWebResponse)
async def read_fabrication_method(
    fabrication_method_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetFabricationMethod = Depends(get_fabrication_method_use_case),
) -> FabricationMethodWebResponse:
    result = await use_case.execute(fabrication_method_id=fabrication_method_id)
    return FabricationMethodWebResponse.model_validate(result.model_dump())


@router.get("/{fabrication_method_id}/changelog", response_model=list[str])
async def read_fabrication_method_changelog(
    fabrication_method_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetFabricationMethod = Depends(get_fabrication_method_use_case),
) -> list[str]:
    return await use_case.changelog(fabrication_method_id)


@router.put("/{fabrication_method_id}", response_model=FabricationMethodWebResponse)
async def update_fabrication_method(
    fabrication_method_id: int,
    body: FabricationMethodUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateFabricationMethod = Depends(get_update_fabrication_method_use_case),
) -> FabricationMethodWebResponse:
    cmd = UpdateFabricationMethodCommand(**body.model_dump())
    result = await use_case.execute(
        actor=actor, fabrication_method_id=fabrication_method_id, cmd=cmd
    )
    return FabricationMethodWebResponse.model_validate(result.model_dump())


@router.post("/{fabrication_method_id}/archive", response_model=FabricationMethodWebResponse)
async def archive_fabrication_method(
    fabrication_method_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ArchiveFabricationMethod = Depends(get_archive_fabrication_method_use_case),
) -> FabricationMethodWebResponse:
    result = await use_case.execute(actor=actor, fabrication_method_id=fabrication_method_id)
    return FabricationMethodWebResponse.model_validate(result.model_dump())


@router.post("/{fabrication_method_id}/restore", response_model=FabricationMethodWebResponse)
async def restore_fabrication_method(
    fabrication_method_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RestoreFabricationMethod = Depends(get_restore_fabrication_method_use_case),
) -> FabricationMethodWebResponse:
    result = await use_case.execute(actor=actor, fabrication_method_id=fabrication_method_id)
    return FabricationMethodWebResponse.model_validate(result.model_dump())


@router.post("/{fabrication_method_id}/move", status_code=status.HTTP_204_NO_CONTENT)
async def move_fabrication_method(
    fabrication_method_id: int,
    body: ListMoveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: MoveFabricationMethod = Depends(get_move_fabrication_method_use_case),
) -> None:
    """Moves the entry one place up or down in the order pickers offer."""
    await use_case.execute(actor, fabrication_method_id, body.direction)


@router.post("/{fabrication_method_id}/place", status_code=status.HTTP_204_NO_CONTENT)
async def place_fabrication_method(
    fabrication_method_id: int,
    body: ListPlaceRequest,
    actor: User = Depends(get_current_active_user),
    use_case: PlaceFabricationMethod = Depends(get_place_fabrication_method_use_case),
) -> None:
    """Puts the method next to another one, as dragging its row does."""
    await use_case.execute(
        actor, fabrication_method_id, after_id=body.after_id, before_id=body.before_id
    )
