"""Use case factories: admin acknowledgement management and the acting
user's own announcements.
"""

from fastapi import Depends

from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_acknowledgement_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_platform_settings_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_session_repo
from src.modules.platform.application.use_cases.acknowledgement.announcements_for_user import (
    AcknowledgeAnnouncement,
)
from src.modules.platform.application.use_cases.acknowledgement.announcements_for_user import (
    GetMyAnnouncements,
)
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
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.acknowledgement_repository import (
    IAcknowledgementRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_list_acknowledgements_use_case(
    ack_repo: IAcknowledgementRepository = Depends(get_acknowledgement_repo),
) -> ListAcknowledgements:
    return ListAcknowledgements(ack_repo)


def get_create_acknowledgement_use_case(
    ack_repo: IAcknowledgementRepository = Depends(get_acknowledgement_repo),
    user_repo: IUserRepository = Depends(get_user_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateAcknowledgement:
    return CreateAcknowledgement(ack_repo, user_repo, uow=uow)


def get_set_acknowledgement_enabled_use_case(
    ack_repo: IAcknowledgementRepository = Depends(get_acknowledgement_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SetAcknowledgementEnabled:
    return SetAcknowledgementEnabled(ack_repo, uow=uow)


def get_delete_acknowledgement_use_case(
    ack_repo: IAcknowledgementRepository = Depends(get_acknowledgement_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DeleteAcknowledgement:
    return DeleteAcknowledgement(ack_repo, uow=uow)


def get_list_acknowledgement_recipients_use_case(
    ack_repo: IAcknowledgementRepository = Depends(get_acknowledgement_repo),
) -> ListAcknowledgementRecipients:
    return ListAcknowledgementRecipients(ack_repo)


def get_my_announcements_use_case(
    ack_repo: IAcknowledgementRepository = Depends(get_acknowledgement_repo),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    session_repo: IUserSessionRepository = Depends(get_user_session_repo),
) -> GetMyAnnouncements:
    return GetMyAnnouncements(ack_repo, settings_repo, session_repo)


def get_acknowledge_announcement_use_case(
    ack_repo: IAcknowledgementRepository = Depends(get_acknowledgement_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> AcknowledgeAnnouncement:
    return AcknowledgeAnnouncement(ack_repo, uow=uow)
