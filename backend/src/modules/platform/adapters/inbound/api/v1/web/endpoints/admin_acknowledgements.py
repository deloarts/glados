"""
Admin CRUD for acknowledgements. Reads require read:settings, writes
require write:settings (enforced in the use cases, mirrors
endpoints/webhooks.py). Mounted at /admin/acknowledgements.
"""

from uuid import UUID

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.acknowledgements import (
    get_create_acknowledgement_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.acknowledgements import (
    get_delete_acknowledgement_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.acknowledgements import (
    get_list_acknowledgement_recipients_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.acknowledgements import (
    get_list_acknowledgements_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.acknowledgements import (
    get_set_acknowledgement_enabled_use_case,
)
from src.modules.platform.adapters.inbound.api.schemas.acknowledgement_schema import (
    AcknowledgementRecipientResult,
)
from src.modules.platform.adapters.inbound.api.schemas.acknowledgement_schema import (
    AcknowledgementSummaryResult,
)
from src.modules.platform.adapters.inbound.api.schemas.acknowledgement_schema import (
    CreateAcknowledgementRequest,
)
from src.modules.platform.adapters.inbound.api.schemas.acknowledgement_schema import (
    SetAcknowledgementEnabledRequest,
)
from src.modules.platform.application.dto.acknowledgement_dto import CreateAcknowledgementCommand
from src.modules.platform.application.use_cases.acknowledgement.manage_acknowledgements import (
    CreateAcknowledgement,
)
from src.modules.platform.application.use_cases.acknowledgement.manage_acknowledgements import (
    DeleteAcknowledgement,
)
from src.modules.platform.application.use_cases.acknowledgement.manage_acknowledgements import (
    ListAcknowledgementRecipients,
)
from src.modules.platform.application.use_cases.acknowledgement.manage_acknowledgements import (
    ListAcknowledgements,
)
from src.modules.platform.application.use_cases.acknowledgement.manage_acknowledgements import (
    SetAcknowledgementEnabled,
)
from src.modules.platform.domain.entities.user import User

router = APIRouter()


# Deliberately unpaginated: bounded per-instance collection, same
# reasoning as webhooks.py's subscription list.
@router.get("/", response_model=list[AcknowledgementSummaryResult])
async def read_acknowledgements(
    actor: User = Depends(get_current_active_user),
    use_case: ListAcknowledgements = Depends(get_list_acknowledgements_use_case),
) -> list[AcknowledgementSummaryResult]:
    return await use_case.execute(actor=actor)


@router.post("/", response_model=AcknowledgementSummaryResult, status_code=status.HTTP_201_CREATED)
async def create_acknowledgement(
    body: CreateAcknowledgementRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateAcknowledgement = Depends(get_create_acknowledgement_use_case),
) -> AcknowledgementSummaryResult:
    cmd = CreateAcknowledgementCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.patch("/{public_id}", response_model=AcknowledgementSummaryResult)
async def set_acknowledgement_enabled(
    public_id: UUID,
    body: SetAcknowledgementEnabledRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SetAcknowledgementEnabled = Depends(get_set_acknowledgement_enabled_use_case),
) -> AcknowledgementSummaryResult:
    """Switch an acknowledgement on or off. Only `enabled` may change after
    creation; text, severity, show_when and recipients are fixed."""
    return await use_case.execute(actor=actor, public_id=public_id, enabled=body.enabled)


@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_acknowledgement(
    public_id: UUID,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteAcknowledgement = Depends(get_delete_acknowledgement_use_case),
) -> None:
    await use_case.execute(actor=actor, public_id=public_id)


@router.get("/{public_id}/recipients", response_model=list[AcknowledgementRecipientResult])
async def read_acknowledgement_recipients(
    public_id: UUID,
    actor: User = Depends(get_current_active_user),
    use_case: ListAcknowledgementRecipients = Depends(get_list_acknowledgement_recipients_use_case),
) -> list[AcknowledgementRecipientResult]:
    return await use_case.execute(actor=actor, public_id=public_id)
