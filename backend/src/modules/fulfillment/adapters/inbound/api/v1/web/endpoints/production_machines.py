"""
ProductionMachine catalogue endpoints. Prefix `/production-machines`,
flat kebab-case, matching this repo's actual convention (see
production_lots.py's docstring).
"""

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_add_machine_downtime_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_archive_production_machine_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_create_machine_calendar_exception_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_create_production_machine_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_default_working_hours_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_delete_machine_calendar_exception_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_delete_machine_downtime_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_delete_machine_working_hours_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_end_machine_downtime_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_machine_calendar_exceptions_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_machine_downtimes_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_machine_working_hours_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_move_production_machine_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_place_production_machine_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_production_machine_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_production_machines_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_restore_production_machine_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_set_default_working_hours_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_set_machine_working_hours_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_update_machine_calendar_exception_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_update_machine_downtime_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_update_production_machine_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_machine_schema import (
    MachineCalendarExceptionCreateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_machine_schema import (
    MachineCalendarExceptionResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_machine_schema import (
    MachineCalendarExceptionUpdateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_machine_schema import (
    MachineDowntimeCreateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_machine_schema import (
    MachineDowntimeEndRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_machine_schema import (
    MachineDowntimeFilterParams,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_machine_schema import (
    MachineDowntimeResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_machine_schema import (
    MachineDowntimeUpdateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_machine_schema import (
    MachineWorkingHoursResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_machine_schema import (
    MachineWorkingHoursSetRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_machine_schema import (
    ProductionMachineCreateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_machine_schema import (
    ProductionMachineFilterParams,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_machine_schema import (
    ProductionMachineResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_machine_schema import (
    ProductionMachineUpdateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_machine_schema import (
    WorkIntervalSchema,
)
from src.modules.fulfillment.application.dto.machine_calendar_dto import (
    CreateMachineCalendarExceptionCommand,
)
from src.modules.fulfillment.application.dto.machine_calendar_dto import (
    MachineCalendarExceptionResult,
)
from src.modules.fulfillment.application.dto.machine_calendar_dto import MachineWorkingHoursResult
from src.modules.fulfillment.application.dto.machine_calendar_dto import (
    SetMachineWorkingHoursCommand,
)
from src.modules.fulfillment.application.dto.machine_calendar_dto import (
    UpdateMachineCalendarExceptionCommand,
)
from src.modules.fulfillment.application.dto.machine_calendar_dto import WorkIntervalDto
from src.modules.fulfillment.application.dto.machine_downtime_dto import AddMachineDowntimeCommand
from src.modules.fulfillment.application.dto.machine_downtime_dto import EndMachineDowntimeCommand
from src.modules.fulfillment.application.dto.machine_downtime_dto import MachineDowntimeResult
from src.modules.fulfillment.application.dto.machine_downtime_dto import (
    UpdateMachineDowntimeCommand,
)
from src.modules.fulfillment.application.dto.production_machine_dto import (
    CreateProductionMachineCommand,
)
from src.modules.fulfillment.application.dto.production_machine_dto import ProductionMachineResult
from src.modules.fulfillment.application.dto.production_machine_dto import (
    UpdateProductionMachineCommand,
)
from src.modules.fulfillment.application.use_cases.production_machine.archive_machine import (
    ArchiveProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.calendar_exceptions import (
    CreateMachineCalendarException,
)
from src.modules.fulfillment.application.use_cases.production_machine.calendar_exceptions import (
    DeleteMachineCalendarException,
)
from src.modules.fulfillment.application.use_cases.production_machine.calendar_exceptions import (
    GetMachineCalendarExceptions,
)
from src.modules.fulfillment.application.use_cases.production_machine.calendar_exceptions import (
    UpdateMachineCalendarException,
)
from src.modules.fulfillment.application.use_cases.production_machine.create_machine import (
    CreateProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.downtimes import (
    AddMachineDowntime,
)
from src.modules.fulfillment.application.use_cases.production_machine.downtimes import (
    DeleteMachineDowntime,
)
from src.modules.fulfillment.application.use_cases.production_machine.downtimes import (
    EndMachineDowntime,
)
from src.modules.fulfillment.application.use_cases.production_machine.downtimes import (
    GetMachineDowntimes,
)
from src.modules.fulfillment.application.use_cases.production_machine.downtimes import (
    UpdateMachineDowntime,
)
from src.modules.fulfillment.application.use_cases.production_machine.get_machine import (
    GetProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.get_machine import (
    GetProductionMachines,
)
from src.modules.fulfillment.application.use_cases.production_machine.move_machine import (
    MoveProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.move_machine import (
    PlaceProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.restore_machine import (
    RestoreProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.update_machine import (
    UpdateProductionMachine,
)
from src.modules.fulfillment.application.use_cases.production_machine.working_hours import (
    DeleteMachineWorkingHours,
)
from src.modules.fulfillment.application.use_cases.production_machine.working_hours import (
    GetDefaultWorkingHours,
)
from src.modules.fulfillment.application.use_cases.production_machine.working_hours import (
    GetMachineWorkingHours,
)
from src.modules.fulfillment.application.use_cases.production_machine.working_hours import (
    SetDefaultWorkingHours,
)
from src.modules.fulfillment.application.use_cases.production_machine.working_hours import (
    SetMachineWorkingHours,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.list_move_schema import ListMoveRequest
from src.modules.platform.adapters.inbound.api.schemas.list_move_schema import ListPlaceRequest
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[ProductionMachineResponse])
async def read_production_machines(
    params: ProductionMachineFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    use_case: GetProductionMachines = Depends(get_production_machines_use_case),
) -> PageResponse[ProductionMachineResult]:
    result = await use_case.execute(params.to_dto())
    return PageResponse.from_result(result, params)


@router.post("/", response_model=ProductionMachineResponse, status_code=status.HTTP_201_CREATED)
async def create_production_machine(
    body: ProductionMachineCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateProductionMachine = Depends(get_create_production_machine_use_case),
) -> ProductionMachineResult:
    cmd = CreateProductionMachineCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


# ── Downtime ─────────────────────────────────────────────────────────
#
# Registered before the "/{machine_id}" routes below: FastAPI/Starlette
# matches path *shape*, not the declared parameter type, so a literal
# "/downtimes" request would otherwise be captured by "/{machine_id}"
# first and fail int conversion with a 422 before ever reaching this
# route.


@router.get("/default-working-hours", response_model=dict[int, list[WorkIntervalSchema]])
async def read_default_working_hours(
    _: User = Depends(get_current_active_user),
    use_case: GetDefaultWorkingHours = Depends(get_default_working_hours_use_case),
) -> dict[int, list[WorkIntervalDto]]:
    """The default calendar: the weekly hours of every machine without its
    own override, and of manual work."""
    return await use_case.execute()


@router.put("/default-working-hours", response_model=dict[int, list[WorkIntervalSchema]])
async def set_default_working_hours(
    body: MachineWorkingHoursSetRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SetDefaultWorkingHours = Depends(get_set_default_working_hours_use_case),
) -> dict[int, list[WorkIntervalDto]]:
    """Needs the right to edit machines, not the settings right."""
    return await use_case.execute(actor, SetMachineWorkingHoursCommand(**body.model_dump()))


@router.get("/downtimes", response_model=PageResponse[MachineDowntimeResponse])
async def read_machine_downtimes(
    params: MachineDowntimeFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    use_case: GetMachineDowntimes = Depends(get_machine_downtimes_use_case),
) -> PageResponse[MachineDowntimeResult]:
    result = await use_case.execute(params.to_dto())
    return PageResponse.from_result(result, params)


@router.post(
    "/downtimes", response_model=MachineDowntimeResponse, status_code=status.HTTP_201_CREATED
)
async def add_machine_downtime(
    body: MachineDowntimeCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: AddMachineDowntime = Depends(get_add_machine_downtime_use_case),
) -> MachineDowntimeResult:
    cmd = AddMachineDowntimeCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.put("/downtimes/{downtime_id}", response_model=MachineDowntimeResponse)
async def update_machine_downtime(
    downtime_id: int,
    body: MachineDowntimeUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateMachineDowntime = Depends(get_update_machine_downtime_use_case),
) -> MachineDowntimeResult:
    cmd = UpdateMachineDowntimeCommand(**body.model_dump())
    return await use_case.execute(actor=actor, downtime_id=downtime_id, cmd=cmd)


@router.delete("/downtimes/{downtime_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_machine_downtime(
    downtime_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteMachineDowntime = Depends(get_delete_machine_downtime_use_case),
) -> None:
    await use_case.execute(actor=actor, downtime_id=downtime_id)


@router.post("/downtimes/{downtime_id}/end", response_model=MachineDowntimeResponse)
async def end_machine_downtime(
    downtime_id: int,
    body: MachineDowntimeEndRequest,
    actor: User = Depends(get_current_active_user),
    use_case: EndMachineDowntime = Depends(get_end_machine_downtime_use_case),
) -> MachineDowntimeResult:
    cmd = EndMachineDowntimeCommand(**body.model_dump())
    return await use_case.execute(actor=actor, downtime_id=downtime_id, cmd=cmd)


@router.get("/{machine_id}", response_model=ProductionMachineResponse)
async def read_production_machine(
    machine_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetProductionMachine = Depends(get_production_machine_use_case),
) -> ProductionMachineResult:
    return await use_case.execute(machine_id=machine_id)


@router.patch("/{machine_id}", response_model=ProductionMachineResponse)
async def update_production_machine(
    machine_id: int,
    body: ProductionMachineUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateProductionMachine = Depends(get_update_production_machine_use_case),
) -> ProductionMachineResult:
    cmd = UpdateProductionMachineCommand(**body.model_dump())
    return await use_case.execute(actor=actor, machine_id=machine_id, cmd=cmd)


@router.post("/{machine_id}/archive", response_model=ProductionMachineResponse)
async def archive_production_machine(
    machine_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ArchiveProductionMachine = Depends(get_archive_production_machine_use_case),
) -> ProductionMachineResult:
    return await use_case.execute(actor=actor, machine_id=machine_id)


@router.post("/{machine_id}/restore", response_model=ProductionMachineResponse)
async def restore_production_machine(
    machine_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RestoreProductionMachine = Depends(get_restore_production_machine_use_case),
) -> ProductionMachineResult:
    return await use_case.execute(actor=actor, machine_id=machine_id)


@router.post("/{machine_id}/move", status_code=status.HTTP_204_NO_CONTENT)
async def move_production_machine(
    machine_id: int,
    body: ListMoveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: MoveProductionMachine = Depends(get_move_production_machine_use_case),
) -> None:
    """Moves the machine one place up or down in the hand-kept order."""
    await use_case.execute(actor, machine_id, body.direction)


@router.post("/{machine_id}/place", status_code=status.HTTP_204_NO_CONTENT)
async def place_production_machine(
    machine_id: int,
    body: ListPlaceRequest,
    actor: User = Depends(get_current_active_user),
    use_case: PlaceProductionMachine = Depends(get_place_production_machine_use_case),
) -> None:
    """Puts the machine next to another one, as dragging its row does."""
    await use_case.execute(actor, machine_id, after_id=body.after_id, before_id=body.before_id)


# ── Working hours ──────────────────────────────────────────────────────


@router.get("/{machine_id}/working-hours", response_model=MachineWorkingHoursResponse | None)
async def read_machine_working_hours(
    machine_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetMachineWorkingHours = Depends(get_machine_working_hours_use_case),
) -> MachineWorkingHoursResult | None:
    """None means the machine uses the global default calendar."""
    return await use_case.execute(machine_id=machine_id)


@router.put("/{machine_id}/working-hours", response_model=MachineWorkingHoursResponse)
async def set_machine_working_hours(
    machine_id: int,
    body: MachineWorkingHoursSetRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SetMachineWorkingHours = Depends(get_set_machine_working_hours_use_case),
) -> MachineWorkingHoursResult:
    cmd = SetMachineWorkingHoursCommand(**body.model_dump())
    return await use_case.execute(actor=actor, machine_id=machine_id, cmd=cmd)


@router.delete("/{machine_id}/working-hours", status_code=status.HTTP_204_NO_CONTENT)
async def delete_machine_working_hours(
    machine_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteMachineWorkingHours = Depends(get_delete_machine_working_hours_use_case),
) -> None:
    """Removes the machine's override; it reverts to the global default calendar."""
    await use_case.execute(actor=actor, machine_id=machine_id)


# ── Calendar exceptions ────────────────────────────────────────────────


@router.get(
    "/{machine_id}/calendar-exceptions", response_model=list[MachineCalendarExceptionResponse]
)
async def read_machine_calendar_exceptions(
    machine_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetMachineCalendarExceptions = Depends(get_machine_calendar_exceptions_use_case),
) -> list[MachineCalendarExceptionResult]:
    return await use_case.execute(machine_id=machine_id)


@router.post(
    "/{machine_id}/calendar-exceptions",
    response_model=MachineCalendarExceptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_machine_calendar_exception(
    machine_id: int,
    body: MachineCalendarExceptionCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateMachineCalendarException = Depends(
        get_create_machine_calendar_exception_use_case
    ),
) -> MachineCalendarExceptionResult:
    cmd = CreateMachineCalendarExceptionCommand(**body.model_dump())
    return await use_case.execute(actor=actor, machine_id=machine_id, cmd=cmd)


@router.patch(
    "/calendar-exceptions/{exception_id}", response_model=MachineCalendarExceptionResponse
)
async def update_machine_calendar_exception(
    exception_id: int,
    body: MachineCalendarExceptionUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateMachineCalendarException = Depends(
        get_update_machine_calendar_exception_use_case
    ),
) -> MachineCalendarExceptionResult:
    cmd = UpdateMachineCalendarExceptionCommand(**body.model_dump())
    return await use_case.execute(actor=actor, exception_id=exception_id, cmd=cmd)


@router.delete("/calendar-exceptions/{exception_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_machine_calendar_exception(
    exception_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteMachineCalendarException = Depends(
        get_delete_machine_calendar_exception_use_case
    ),
) -> None:
    await use_case.execute(actor=actor, exception_id=exception_id)
