"""
Web surface customer endpoints.
"""

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.catalogue import get_archive_customer_use_case
from src.modules.catalogue.adapters.inbound.api.deps.catalogue import get_create_customer_use_case
from src.modules.catalogue.adapters.inbound.api.deps.catalogue import get_customer_use_case
from src.modules.catalogue.adapters.inbound.api.deps.catalogue import get_customers_use_case
from src.modules.catalogue.adapters.inbound.api.deps.catalogue import get_restore_customer_use_case
from src.modules.catalogue.adapters.inbound.api.deps.catalogue import get_update_customer_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.customer_schema import CustomerCreateRequest
from src.modules.catalogue.adapters.inbound.api.schemas.customer_schema import CustomerFilterParams
from src.modules.catalogue.adapters.inbound.api.schemas.customer_schema import CustomerResponse
from src.modules.catalogue.adapters.inbound.api.schemas.customer_schema import CustomerUpdateRequest
from src.modules.catalogue.application.dto.customer_dto import CreateCustomerCommand
from src.modules.catalogue.application.dto.customer_dto import UpdateCustomerCommand
from src.modules.catalogue.application.use_cases.customer.archive_customer import ArchiveCustomer
from src.modules.catalogue.application.use_cases.customer.create_customer import CreateCustomer
from src.modules.catalogue.application.use_cases.customer.get_customer import GetCustomer
from src.modules.catalogue.application.use_cases.customer.get_customer import GetCustomers
from src.modules.catalogue.application.use_cases.customer.restore_customer import RestoreCustomer
from src.modules.catalogue.application.use_cases.customer.update_customer import UpdateCustomer
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


# ── GET /customers/ ───────────────────────────────────────────────────


@router.get("/", response_model=PageResponse[CustomerResponse])
async def read_customers(
    params: CustomerFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    use_case: GetCustomers = Depends(get_customers_use_case),
) -> PageResponse[CustomerResponse]:
    result = await use_case.execute(params.to_dto())
    return PageResponse.from_result(result, params, item_model=CustomerResponse)


# ── POST /customers/ ──────────────────────────────────────────────────


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    body: CustomerCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateCustomer = Depends(get_create_customer_use_case),
) -> CustomerResponse:
    cmd = CreateCustomerCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, cmd=cmd)
    return CustomerResponse.model_validate(result.model_dump())


# ── GET /customers/{customer_id} ──────────────────────────────────────


@router.get("/{customer_id}", response_model=CustomerResponse)
async def read_customer_by_id(
    customer_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetCustomer = Depends(get_customer_use_case),
) -> CustomerResponse:
    result = await use_case.execute(customer_id=customer_id)
    return CustomerResponse.model_validate(result.model_dump())


# ── PUT /customers/{customer_id} ──────────────────────────────────────


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    body: CustomerUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateCustomer = Depends(get_update_customer_use_case),
) -> CustomerResponse:
    cmd = UpdateCustomerCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, customer_id=customer_id, cmd=cmd)
    return CustomerResponse.model_validate(result.model_dump())


# ── POST /customers/{customer_id}/archive ─────────────────────────────


@router.post("/{customer_id}/archive", response_model=CustomerResponse)
async def archive_customer(
    customer_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ArchiveCustomer = Depends(get_archive_customer_use_case),
) -> CustomerResponse:
    result = await use_case.execute(actor=actor, customer_id=customer_id)
    return CustomerResponse.model_validate(result.model_dump())


# ── POST /customers/{customer_id}/restore ─────────────────────────────


@router.post("/{customer_id}/restore", response_model=CustomerResponse)
async def restore_customer(
    customer_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RestoreCustomer = Depends(get_restore_customer_use_case),
) -> CustomerResponse:
    result = await use_case.execute(actor=actor, customer_id=customer_id)
    return CustomerResponse.model_validate(result.model_dump())
