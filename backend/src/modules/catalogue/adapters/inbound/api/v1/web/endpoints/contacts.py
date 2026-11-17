"""
Web surface contact endpoints. Reading needs read:contacts and every write
needs write:contacts, both checked in the use cases. Contacts are archived,
never deleted, and an anonymised contact keeps its row without its personal
data.
"""

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.contacts import get_anonymise_contact_use_case
from src.modules.catalogue.adapters.inbound.api.deps.contacts import get_archive_contact_use_case
from src.modules.catalogue.adapters.inbound.api.deps.contacts import get_contact_use_case
from src.modules.catalogue.adapters.inbound.api.deps.contacts import get_contacts_use_case
from src.modules.catalogue.adapters.inbound.api.deps.contacts import get_create_contact_use_case
from src.modules.catalogue.adapters.inbound.api.deps.contacts import get_restore_contact_use_case
from src.modules.catalogue.adapters.inbound.api.deps.contacts import get_update_contact_use_case
from src.modules.catalogue.adapters.inbound.api.schemas.contact_schema import ContactCreateRequest
from src.modules.catalogue.adapters.inbound.api.schemas.contact_schema import ContactFilterParams
from src.modules.catalogue.adapters.inbound.api.schemas.contact_schema import ContactResponse
from src.modules.catalogue.adapters.inbound.api.schemas.contact_schema import ContactUpdateRequest
from src.modules.catalogue.application.dto.contact_dto import CreateContactCommand
from src.modules.catalogue.application.dto.contact_dto import UpdateContactCommand
from src.modules.catalogue.application.use_cases.contact.anonymise_contact import AnonymiseContact
from src.modules.catalogue.application.use_cases.contact.archive_contact import ArchiveContact
from src.modules.catalogue.application.use_cases.contact.archive_contact import RestoreContact
from src.modules.catalogue.application.use_cases.contact.create_contact import CreateContact
from src.modules.catalogue.application.use_cases.contact.get_contact import GetContact
from src.modules.catalogue.application.use_cases.contact.get_contact import GetContacts
from src.modules.catalogue.application.use_cases.contact.update_contact import UpdateContact
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[ContactResponse])
async def read_contacts(
    params: ContactFilterParams = Depends(),
    actor: User = Depends(get_current_active_user),
    use_case: GetContacts = Depends(get_contacts_use_case),
) -> PageResponse[ContactResponse]:
    result = await use_case.execute(actor, params.to_dto())
    return PageResponse.from_result(result, params, item_model=ContactResponse)


@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    body: ContactCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateContact = Depends(get_create_contact_use_case),
) -> ContactResponse:
    result = await use_case.execute(actor, CreateContactCommand(**body.model_dump()))
    return ContactResponse.model_validate(result.model_dump())


@router.get("/{contact_id}", response_model=ContactResponse)
async def read_contact(
    contact_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetContact = Depends(get_contact_use_case),
) -> ContactResponse:
    result = await use_case.execute(actor, contact_id)
    return ContactResponse.model_validate(result.model_dump())


@router.put("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: int,
    body: ContactUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateContact = Depends(get_update_contact_use_case),
) -> ContactResponse:
    result = await use_case.execute(actor, contact_id, UpdateContactCommand(**body.model_dump()))
    return ContactResponse.model_validate(result.model_dump())


@router.post("/{contact_id}/archive", response_model=ContactResponse)
async def archive_contact(
    contact_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ArchiveContact = Depends(get_archive_contact_use_case),
) -> ContactResponse:
    result = await use_case.execute(actor, contact_id)
    return ContactResponse.model_validate(result.model_dump())


@router.post("/{contact_id}/restore", response_model=ContactResponse)
async def restore_contact(
    contact_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RestoreContact = Depends(get_restore_contact_use_case),
) -> ContactResponse:
    result = await use_case.execute(actor, contact_id)
    return ContactResponse.model_validate(result.model_dump())


@router.post("/{contact_id}/anonymise", response_model=ContactResponse)
async def anonymise_contact(
    contact_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: AnonymiseContact = Depends(get_anonymise_contact_use_case),
) -> ContactResponse:
    """Blanks the contact's personal data and archives it, for good."""
    result = await use_case.execute(actor, contact_id)
    return ContactResponse.model_validate(result.model_dump())
