"""
Web surface endpoints for the contacts of products and projects and for the
usage of contacts. Reading needs read:contacts and every change
write:contacts, both checked in the use cases. Every change answers the
owner's whole contact list as it is afterwards.
"""

from fastapi import Depends
from fastapi import Query
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.adapters.inbound.api.deps.contact_links import get_contact_usage_use_case
from src.modules.workspace.adapters.inbound.api.deps.contact_links import (
    get_link_product_contact_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.contact_links import (
    get_link_project_contact_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.contact_links import (
    get_product_contacts_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.contact_links import (
    get_project_contacts_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.contact_links import (
    get_set_product_contact_meeting_notes_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.contact_links import (
    get_set_project_contact_meeting_notes_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.contact_links import (
    get_unlink_product_contact_use_case,
)
from src.modules.workspace.adapters.inbound.api.deps.contact_links import (
    get_unlink_project_contact_use_case,
)
from src.modules.workspace.adapters.inbound.api.schemas.contact_link_schema import (
    ContactLinkCreateRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.contact_link_schema import (
    ContactLinkUpdateRequest,
)
from src.modules.workspace.adapters.inbound.api.schemas.contact_link_schema import (
    ContactUsageResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.contact_link_schema import (
    ProductContactResponse,
)
from src.modules.workspace.adapters.inbound.api.schemas.contact_link_schema import (
    ProjectContactResponse,
)
from src.modules.workspace.application.dto.contact_link_dto import LinkContactCommand
from src.modules.workspace.application.dto.contact_link_dto import ProductContactResult
from src.modules.workspace.application.dto.contact_link_dto import ProjectContactResult
from src.modules.workspace.application.use_cases.contact_link.contact_usage import GetContactUsage
from src.modules.workspace.application.use_cases.contact_link.product_contacts import (
    GetProductContacts,
)
from src.modules.workspace.application.use_cases.contact_link.product_contacts import (
    LinkProductContact,
)
from src.modules.workspace.application.use_cases.contact_link.product_contacts import (
    SetProductContactMeetingNotes,
)
from src.modules.workspace.application.use_cases.contact_link.product_contacts import (
    UnlinkProductContact,
)
from src.modules.workspace.application.use_cases.contact_link.project_contacts import (
    GetProjectContacts,
)
from src.modules.workspace.application.use_cases.contact_link.project_contacts import (
    LinkProjectContact,
)
from src.modules.workspace.application.use_cases.contact_link.project_contacts import (
    SetProjectContactMeetingNotes,
)
from src.modules.workspace.application.use_cases.contact_link.project_contacts import (
    UnlinkProjectContact,
)

product_router = APIRouter()
project_router = APIRouter()
usage_router = APIRouter()

# The Used In column asks for one page of the contacts table at a time.
_MAX_USAGE_IDS = 200


def _products(results: list[ProductContactResult]) -> list[ProductContactResponse]:
    return [ProductContactResponse.model_validate(r.model_dump()) for r in results]


def _projects(results: list[ProjectContactResult]) -> list[ProjectContactResponse]:
    return [ProjectContactResponse.model_validate(r.model_dump()) for r in results]


# ── /products/{product_id}/contacts ───────────────────────────────────


@product_router.get("/{product_id}/contacts", response_model=list[ProductContactResponse])
async def read_product_contacts(
    product_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetProductContacts = Depends(get_product_contacts_use_case),
) -> list[ProductContactResponse]:
    return _products(await use_case.execute(actor, product_id))


@product_router.post("/{product_id}/contacts", response_model=list[ProductContactResponse])
async def link_product_contact(
    product_id: int,
    body: ContactLinkCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: LinkProductContact = Depends(get_link_product_contact_use_case),
) -> list[ProductContactResponse]:
    cmd = LinkContactCommand(**body.model_dump())
    return _products(await use_case.execute(actor, product_id, cmd))


@product_router.put(
    "/{product_id}/contacts/{contact_id}", response_model=list[ProductContactResponse]
)
async def update_product_contact(
    product_id: int,
    contact_id: int,
    body: ContactLinkUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SetProductContactMeetingNotes = Depends(
        get_set_product_contact_meeting_notes_use_case
    ),
) -> list[ProductContactResponse]:
    return _products(
        await use_case.execute(actor, product_id, contact_id, body.receives_meeting_notes)
    )


@product_router.delete(
    "/{product_id}/contacts/{contact_id}", response_model=list[ProductContactResponse]
)
async def unlink_product_contact(
    product_id: int,
    contact_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: UnlinkProductContact = Depends(get_unlink_product_contact_use_case),
) -> list[ProductContactResponse]:
    return _products(await use_case.execute(actor, product_id, contact_id))


# ── /projects/{project_id}/contacts ───────────────────────────────────


@project_router.get("/{project_id}/contacts", response_model=list[ProjectContactResponse])
async def read_project_contacts(
    project_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetProjectContacts = Depends(get_project_contacts_use_case),
) -> list[ProjectContactResponse]:
    """The product's contacts, inherited, then the project's own."""
    return _projects(await use_case.execute(actor, project_id))


@project_router.post("/{project_id}/contacts", response_model=list[ProjectContactResponse])
async def link_project_contact(
    project_id: int,
    body: ContactLinkCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: LinkProjectContact = Depends(get_link_project_contact_use_case),
) -> list[ProjectContactResponse]:
    cmd = LinkContactCommand(**body.model_dump())
    return _projects(await use_case.execute(actor, project_id, cmd))


@project_router.put(
    "/{project_id}/contacts/{contact_id}", response_model=list[ProjectContactResponse]
)
async def update_project_contact(
    project_id: int,
    contact_id: int,
    body: ContactLinkUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SetProjectContactMeetingNotes = Depends(
        get_set_project_contact_meeting_notes_use_case
    ),
) -> list[ProjectContactResponse]:
    """Sets the flag for the project, an inherited contact included, which
    is how a project mutes one of its product's contacts."""
    return _projects(
        await use_case.execute(actor, project_id, contact_id, body.receives_meeting_notes)
    )


@project_router.delete(
    "/{project_id}/contacts/{contact_id}", response_model=list[ProjectContactResponse]
)
async def unlink_project_contact(
    project_id: int,
    contact_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: UnlinkProjectContact = Depends(get_unlink_project_contact_use_case),
) -> list[ProjectContactResponse]:
    """Unlinks one of the project's own contacts; an inherited one answers 409."""
    return _projects(await use_case.execute(actor, project_id, contact_id))


# ── /contact-usage ────────────────────────────────────────────────────


@usage_router.get("/", response_model=list[ContactUsageResponse])
async def read_contact_usage(
    contact_ids: list[int] = Query(default=[], max_length=_MAX_USAGE_IDS),
    actor: User = Depends(get_current_active_user),
    use_case: GetContactUsage = Depends(get_contact_usage_use_case),
) -> list[ContactUsageResponse]:
    """The products and projects that link each of the contacts, one entry
    per contact asked for."""
    results = await use_case.execute(actor, contact_ids)
    return [ContactUsageResponse.model_validate(r.model_dump()) for r in results]
