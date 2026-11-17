"""
Converts between User domain entity, DTOs, and the persistence ORM model.
This is the only place that knows about all three representations.
"""

from src.modules.platform.application.dto.user_dto import PublicUserResult
from src.modules.platform.application.dto.user_dto import RfidIdentityResult
from src.modules.platform.application.dto.user_dto import UserPdmLinkResult
from src.modules.platform.application.dto.user_dto import UserResult
from src.modules.platform.application.dto.user_dto import UserSummaryResult
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.entities.user_pdm_link import UserPdmLink


class UserMapper:
    @staticmethod
    def to_public_result(entity: User) -> PublicUserResult:
        """Non-sensitive subset for embedding as a live user reference."""
        return PublicUserResult(
            id=entity.id,
            public_id=entity.public_id,
            username=entity.username,
            full_name=entity.full_name,
            has_avatar=bool(entity.avatar_key),
        )

    @staticmethod
    def to_summary_result(entity: User) -> UserSummaryResult:
        """The reduced view every signed-in user may read."""
        return UserSummaryResult(
            id=entity.id,
            public_id=entity.public_id,
            username=entity.username,
            full_name=entity.full_name,
            is_active=entity.is_active,
            is_systemuser=entity.is_systemuser,
            is_service_account=entity.is_service_account,
            is_shared_account=entity.is_shared_account,
            has_avatar=bool(entity.avatar_key),
        )

    @staticmethod
    def to_rfid_identity_result(entity: User) -> RfidIdentityResult:
        """Who an RFID tag belongs to, nothing more."""
        return RfidIdentityResult(
            id=entity.id,
            public_id=entity.public_id,
            username=entity.username,
            full_name=entity.full_name,
        )

    @staticmethod
    def to_result(entity: User, pdm_links: list[UserPdmLink] | None = None) -> UserResult:
        """Domain entity → application result DTO. `pdm_links` is a
        separate repository query (UserPdmLink is not denormalized onto
        User), so callers building a full UserResult pass in
        IUserPdmLinkRepository.list_by_user(entity.id)'s result; omitting
        it (None) reports no links, for a caller that only needs the rest
        of the shape."""
        return UserResult(
            id=entity.id,
            public_id=entity.public_id,
            username=entity.username,
            full_name=entity.full_name,
            email=entity.email,
            created=entity.created,
            language=entity.language,
            date_format=entity.date_format,
            start_page=entity.start_page,
            theme_preset=entity.theme_preset,
            theme_surface=entity.theme_surface,
            theme_primary=entity.theme_primary,
            theme_dark_mode=entity.theme_dark_mode,
            button_flat_style=entity.button_flat_style,
            table_gridlines=entity.table_gridlines,
            table_striped_rows=entity.table_striped_rows,
            rfid_configured=entity.rfid_lookup is not None,
            pdm_links=[
                UserPdmLinkResult(
                    pdm_user_id=link.pdm_user_id,
                    pdm_username=link.pdm_username,
                    linked_at=link.linked_at,
                )
                for link in (pdm_links or [])
            ],
            is_active=entity.is_active,
            is_systemuser=entity.is_systemuser,
            is_service_account=entity.is_service_account,
            is_shared_account=entity.is_shared_account,
            auth_provider=entity.auth_provider,
            member_ids=list(entity.member_ids),
            group_ids=list(entity.group_ids),
            permissions=entity.effective_permissions,
            direct_permissions=list(entity.permissions),
            last_logged_in=entity.last_logged_in,
            totp_enabled=entity.totp_enabled,
            has_avatar=bool(entity.avatar_key),
        )
