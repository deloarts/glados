"""
Resolves a SOLIDWORKS PDM Web API user to the Glados User it corresponds
to, so PDM ingest can attribute a changelog line, the "last changed by"
column and, when enabled, the approver to the person who actually
released the file in the vault instead of always the system actor. Shared
by IngestPdmFile (per-file attribution) and
application.use_cases.admin_settings.list_pdm_users.ListPdmUsers (the
admin console's own same-identity guess for a not-yet-linked vault user).
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.repositories.user_pdm_link_repository import (
    IUserPdmLinkRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository


async def resolve_pdm_user(
    link_repo: IUserPdmLinkRepository,
    user_repo: IUserRepository,
    pdm_user_id: int | None,
    pdm_username: str,
) -> User | None:
    """An explicit link (UserPdmLink, set through LinkPdmUsers) wins over a
    username guess; a case-insensitive username match against
    `pdm_username` is the fallback for a vault user nobody has linked yet.
    Returns None when neither resolves; callers then fall back to the
    PDM username as plain text rather than a Glados User, never raising."""
    if pdm_user_id is not None:
        link = await link_repo.get_by_pdm_user_id(pdm_user_id)
        if link is not None:
            linked = await user_repo.get_by_id(link.user_id)
            if linked is not None:
                return linked
    username = pdm_username.strip()
    if not username:
        return None
    return await user_repo.get_by_username_ci(username)
