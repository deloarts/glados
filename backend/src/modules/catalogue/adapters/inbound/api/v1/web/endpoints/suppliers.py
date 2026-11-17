"""
Supplier endpoints, manages the vendor master data referenced by
catalogue items, orders and order items.
"""

from datetime import tzinfo

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.catalogue import get_archive_supplier_use_case
from src.modules.catalogue.adapters.inbound.api.deps.catalogue import get_create_supplier_use_case
from src.modules.catalogue.adapters.inbound.api.deps.catalogue import get_restore_supplier_use_case
from src.modules.catalogue.adapters.inbound.api.deps.catalogue import get_supplier_use_case
from src.modules.catalogue.adapters.inbound.api.deps.catalogue import get_suppliers_use_case
from src.modules.catalogue.adapters.inbound.api.deps.catalogue import get_update_supplier_use_case
from src.modules.catalogue.adapters.inbound.api.deps.contacts import (
    get_supplier_mail_recipients_use_case,
)
from src.modules.catalogue.adapters.inbound.api.schemas.contact_schema import (
    SupplierMailRecipientsResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.supplier_schema import SupplierCreateRequest
from src.modules.catalogue.adapters.inbound.api.schemas.supplier_schema import SupplierFilterParams
from src.modules.catalogue.adapters.inbound.api.schemas.supplier_schema import SupplierUpdateRequest
from src.modules.catalogue.adapters.inbound.api.schemas.supplier_schema import SupplierWebResponse
from src.modules.catalogue.application.dto.supplier_dto import CreateSupplierCommand
from src.modules.catalogue.application.dto.supplier_dto import UpdateSupplierCommand
from src.modules.catalogue.application.use_cases.contact.get_supplier_mail_recipients import (
    GetSupplierMailRecipients,
)
from src.modules.catalogue.application.use_cases.supplier.archive_supplier import ArchiveSupplier
from src.modules.catalogue.application.use_cases.supplier.create_supplier import CreateSupplier
from src.modules.catalogue.application.use_cases.supplier.get_supplier import GetSupplier
from src.modules.catalogue.application.use_cases.supplier.get_supplier import GetSuppliers
from src.modules.catalogue.application.use_cases.supplier.restore_supplier import RestoreSupplier
from src.modules.catalogue.application.use_cases.supplier.update_supplier import UpdateSupplier
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[SupplierWebResponse])
async def read_suppliers(
    params: SupplierFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    zone: tzinfo = Depends(get_tenant_zone),
    use_case: GetSuppliers = Depends(get_suppliers_use_case),
) -> PageResponse[SupplierWebResponse]:
    result = await use_case.execute(params.to_dto(zone))
    return PageResponse.from_result(result, params, item_model=SupplierWebResponse)


@router.post("/", response_model=SupplierWebResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    body: SupplierCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateSupplier = Depends(get_create_supplier_use_case),
) -> SupplierWebResponse:
    cmd = CreateSupplierCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, cmd=cmd)
    return SupplierWebResponse.model_validate(result.model_dump())


@router.get("/{supplier_id}", response_model=SupplierWebResponse)
async def read_supplier(
    supplier_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetSupplier = Depends(get_supplier_use_case),
) -> SupplierWebResponse:
    result = await use_case.execute(supplier_id=supplier_id)
    return SupplierWebResponse.model_validate(result.model_dump())


@router.get("/{supplier_id}/changelog", response_model=list[str])
async def read_supplier_changelog(
    supplier_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetSupplier = Depends(get_supplier_use_case),
) -> list[str]:
    return await use_case.changelog(supplier_id)


@router.put("/{supplier_id}", response_model=SupplierWebResponse)
async def update_supplier(
    supplier_id: int,
    body: SupplierUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateSupplier = Depends(get_update_supplier_use_case),
) -> SupplierWebResponse:
    cmd = UpdateSupplierCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, supplier_id=supplier_id, cmd=cmd)
    return SupplierWebResponse.model_validate(result.model_dump())


@router.post("/{supplier_id}/archive", response_model=SupplierWebResponse)
async def archive_supplier(
    supplier_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ArchiveSupplier = Depends(get_archive_supplier_use_case),
) -> SupplierWebResponse:
    result = await use_case.execute(actor=actor, supplier_id=supplier_id)
    return SupplierWebResponse.model_validate(result.model_dump())


@router.post("/{supplier_id}/restore", response_model=SupplierWebResponse)
async def restore_supplier(
    supplier_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RestoreSupplier = Depends(get_restore_supplier_use_case),
) -> SupplierWebResponse:
    result = await use_case.execute(actor=actor, supplier_id=supplier_id)
    return SupplierWebResponse.model_validate(result.model_dump())


@router.get("/{supplier_id}/mail-recipients", response_model=SupplierMailRecipientsResponse)
async def read_supplier_mail_recipients(
    supplier_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetSupplierMailRecipients = Depends(get_supplier_mail_recipients_use_case),
) -> SupplierMailRecipientsResponse:
    """The supplier's contacts flagged for its request mails and its order
    mails. Needs read:contacts or send:mail."""
    result = await use_case.execute(actor, supplier_id)
    return SupplierMailRecipientsResponse.model_validate(result.model_dump())
