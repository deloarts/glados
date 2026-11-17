"""
Web surface user endpoints. Thin by design:
  parse HTTP → call use case → return HTTP response.

No permission checks here, those live in domain/services/user_rules.py.
No DB calls, those live in the repository.
No business logic, that lives in the use cases.
"""

from fastapi import Depends
from fastapi import Request
from fastapi import Response
from fastapi import UploadFile
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.passkeys import get_reset_user_passkeys_use_case
from src.modules.platform.adapters.inbound.api.deps.passkeys import get_user_passkeys_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_create_user_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_delete_user_avatar_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_delete_user_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_force_logout_all_users_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_force_logout_user_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_reset_user_totp_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_update_user_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_upload_user_avatar_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_user_avatar_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_user_directory_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_user_use_case
from src.modules.platform.adapters.inbound.api.deps.users import get_users_use_case
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.adapters.inbound.api.schemas.passkey_schema import PasskeyResult
from src.modules.platform.adapters.inbound.api.schemas.session_schema import RevokedCountResult
from src.modules.platform.adapters.inbound.api.schemas.user_schema import UserCreateRequest
from src.modules.platform.adapters.inbound.api.schemas.user_schema import UserDirectoryFilterParams
from src.modules.platform.adapters.inbound.api.schemas.user_schema import UserFilterParams
from src.modules.platform.adapters.inbound.api.schemas.user_schema import UserResponse
from src.modules.platform.adapters.inbound.api.schemas.user_schema import UserSummaryResponse
from src.modules.platform.adapters.inbound.api.schemas.user_schema import UserUpdateRequest
from src.modules.platform.adapters.inbound.api.upload_limits import max_upload_size
from src.modules.platform.adapters.inbound.api.v1.auth.login_responses import client_ip
from src.modules.platform.application.dto.user_dto import CreateUserCommand
from src.modules.platform.application.dto.user_dto import UpdateUserCommand
from src.modules.platform.application.dto.user_dto import UserResult
from src.modules.platform.application.use_cases.passkey.manage_passkeys import GetUserPasskeys
from src.modules.platform.application.use_cases.passkey.manage_passkeys import ResetUserPasskeys
from src.modules.platform.application.use_cases.user.create_user import CreateUser
from src.modules.platform.application.use_cases.user.delete_user import DeleteUser
from src.modules.platform.application.use_cases.user.delete_user_avatar import DeleteUserAvatar
from src.modules.platform.application.use_cases.user.force_logout_all_users import (
    ForceLogoutAllUsers,
)
from src.modules.platform.application.use_cases.user.force_logout_user import ForceLogoutUser
from src.modules.platform.application.use_cases.user.get_user import GetUser
from src.modules.platform.application.use_cases.user.get_user import GetUserDirectory
from src.modules.platform.application.use_cases.user.get_user import GetUsers
from src.modules.platform.application.use_cases.user.get_user_avatar import GetUserAvatar
from src.modules.platform.application.use_cases.user.reset_user_totp import ResetUserTotp
from src.modules.platform.application.use_cases.user.update_user import UpdateUser
from src.modules.platform.application.use_cases.user.upload_user_avatar import (
    MAX_BYTES as AVATAR_MAX_BYTES,
)
from src.modules.platform.application.use_cases.user.upload_user_avatar import UploadUserAvatar
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InvalidInputError
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language

router = APIRouter()


# ── GET /users/ ───────────────────────────────────────────────────────


@router.get("/", response_model=PageResponse[UserResponse])
async def read_users(
    params: UserFilterParams = Depends(),
    actor: User = Depends(get_current_active_user),  # see UserRules.assert_can_read_details
    use_case: GetUsers = Depends(get_users_use_case),
) -> PageResponse[UserResponse]:
    """The full user view for user administration, with filtering, search,
    sorting and pagination. Requires read:settings; every other user reads
    GET /users/directory."""
    result = await use_case.execute(actor=actor, filters=params.to_dto())
    return PageResponse.from_result(result, params, item_model=UserResponse)


# ── GET /users/directory ──────────────────────────────────────────────


@router.get("/directory", response_model=PageResponse[UserSummaryResponse])
async def read_user_directory(
    params: UserDirectoryFilterParams = Depends(),
    _: User = Depends(get_current_active_user),  # any authenticated user may list
    use_case: GetUserDirectory = Depends(get_user_directory_use_case),
) -> PageResponse[UserSummaryResponse]:
    """The reduced user list for pickers and name lookups: id, username,
    name, active state, the account kind and whether an avatar exists."""
    result = await use_case.execute(params.to_dto())
    return PageResponse.from_result(result, params, item_model=UserSummaryResponse)


# ── POST /users/ ──────────────────────────────────────────────────────


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    actor: User = Depends(get_current_active_user),  # see UserRules.assert_can_create
    use_case: CreateUser = Depends(get_create_user_use_case),
) -> UserResult:
    """Create a new user. Sends a welcome email on success."""
    cmd = CreateUserCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


# ── GET /users/me ─────────────────────────────────────────────────────


@router.get("/me", response_model=UserResponse)
async def read_user_me(
    current_user: User = Depends(get_current_active_user),
    use_case: GetUser = Depends(get_user_use_case),
) -> UserResult:
    """Return the currently authenticated user."""
    return await use_case.execute(actor=current_user, user_id=current_user.id)


# ── POST /users/me/avatar ─────────────────────────────────────────────


@router.post(
    "/me/avatar",
    response_model=UserResponse,
    dependencies=[Depends(max_upload_size(AVATAR_MAX_BYTES))],
)
async def upload_my_avatar(
    file: UploadFile,
    actor: User = Depends(get_current_active_user),
    use_case: UploadUserAvatar = Depends(get_upload_user_avatar_use_case),
) -> UserResult:
    """Upload or replace the current user's avatar image (JPEG/PNG/WebP/GIF, ≤ 5 MB)."""
    data = await file.read()
    return await use_case.execute(
        actor=actor, user_id=actor.id, data=data, content_type=file.content_type or ""
    )


# ── DELETE /users/me/avatar ───────────────────────────────────────────


@router.delete("/me/avatar", response_model=UserResponse)
async def delete_my_avatar(
    actor: User = Depends(get_current_active_user),
    use_case: DeleteUserAvatar = Depends(get_delete_user_avatar_use_case),
) -> UserResult:
    """Remove the current user's avatar."""
    return await use_case.execute(actor=actor, user_id=actor.id)


# ── GET /users/me/avatar ──────────────────────────────────────────────


@router.get("/me/avatar")
async def read_my_avatar(
    actor: User = Depends(get_current_active_user),
    use_case: GetUserAvatar = Depends(get_user_avatar_use_case),
) -> Response:
    """Stream the current user's avatar image bytes."""
    data, content_type = await use_case.execute(user_id=actor.id)
    return Response(
        content=data, media_type=content_type, headers={"Cache-Control": "private, max-age=3600"}
    )


# ── PUT /users/me ─────────────────────────────────────────────────────


@router.put("/me", response_model=UserResponse)
async def update_user_me(
    body: UserUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    use_case: UpdateUser = Depends(get_update_user_use_case),
) -> UserResult:
    """Update own profile. Permission flags are ignored, enforced by domain rules.
    A new password needs `current_password`, see UpdateUser."""
    cmd = UpdateUserCommand(**body.model_dump(exclude_unset=True))
    return await use_case.execute(
        actor=current_user, target_id=current_user.id, cmd=cmd, client_ip=client_ip(request)
    )


# ── PUT /users/me/language ────────────────────────────────────────────


@router.put("/me/language", response_model=UserResponse)
async def update_user_language(
    language: str,
    current_user: User = Depends(get_current_active_user),
    use_case: UpdateUser = Depends(get_update_user_use_case),
) -> UserResult:
    """Update the authenticated user's UI language."""
    if language not in Language.values():
        raise InvalidInputError(f"Unknown language {language!r}.")
    cmd = UpdateUserCommand(language=Language(language))
    return await use_case.execute(actor=current_user, target_id=current_user.id, cmd=cmd)


# ── PUT /users/me/date-format ─────────────────────────────────────────


@router.put("/me/date-format", response_model=UserResponse)
async def update_user_date_format(
    date_format: DateFormat,
    current_user: User = Depends(get_current_active_user),
    use_case: UpdateUser = Depends(get_update_user_use_case),
) -> UserResult:
    """Update how the authenticated user wants dates rendered.

    Presentation only. It needs no explicit validation here, since FastAPI
    rejects any value outside the DateFormat enum before the handler runs.
    """
    cmd = UpdateUserCommand(date_format=date_format)
    return await use_case.execute(actor=current_user, target_id=current_user.id, cmd=cmd)


# ── PUT /users/me/theme ───────────────────────────────────────────────


@router.put("/me/theme", response_model=UserResponse)
async def update_user_theme(
    body: UserUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    use_case: UpdateUser = Depends(get_update_user_use_case),
) -> UserResult:
    """Update the authenticated user's theme (preset, surface, dark mode)."""
    cmd = UpdateUserCommand(
        theme_preset=body.theme_preset,
        theme_surface=body.theme_surface,
        theme_dark_mode=body.theme_dark_mode,
    )
    return await use_case.execute(actor=current_user, target_id=current_user.id, cmd=cmd)


# ── DELETE /users/me/session ─────────────────────────────────────────


@router.delete("/me/session", response_model=UserResponse)
async def logout_me(
    current_user: User = Depends(get_current_active_user),
    use_case: ForceLogoutUser = Depends(get_force_logout_user_use_case),
) -> UserResult:
    """Terminate all active sessions for the current user (self-service force-logout)."""
    return await use_case.execute(actor=current_user, target_id=current_user.id)


# ── DELETE /users/sessions ────────────────────────────────────────────
# Must be registered before /{user_id} so "sessions" is not consumed as a path param.


@router.delete("/sessions", response_model=dict)
async def force_logout_all_users(
    actor: User = Depends(get_current_active_user),
    use_case: ForceLogoutAllUsers = Depends(get_force_logout_all_users_use_case),
) -> dict[str, int]:
    """Force-logout all non-system active users. Requires write:settings."""
    count = await use_case.execute(actor=actor)
    return {"count": count}


# ── GET /users/{user_id} ──────────────────────────────────────────────


@router.get("/{user_id}", response_model=UserResponse)
async def read_user_by_id(
    user_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetUser = Depends(get_user_use_case),
) -> UserResult:
    """The full view of one user. Self, or requires read:settings."""
    return await use_case.execute(actor=actor, user_id=user_id)


# ── DELETE /users/{user_id} ───────────────────────────────────────────


@router.delete("/{user_id}", response_model=UserResponse)
async def delete_user(
    user_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteUser = Depends(get_delete_user_use_case),
) -> UserResult:
    """Soft-delete a user by deactivating their account. All linked data is preserved."""
    return await use_case.execute(actor=actor, target_id=user_id)


# ── DELETE /users/{user_id}/session ──────────────────────────────────


@router.delete("/{user_id}/session", response_model=UserResponse)
async def force_logout_user(
    user_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ForceLogoutUser = Depends(get_force_logout_user_use_case),
) -> UserResult:
    """Force-logout a user by invalidating all their active sessions and PAT."""
    return await use_case.execute(actor=actor, target_id=user_id)


# ── DELETE /users/{user_id}/totp ─────────────────────────────────────


@router.delete("/{user_id}/totp", response_model=UserResponse)
async def reset_user_totp(
    user_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ResetUserTotp = Depends(get_reset_user_totp_use_case),
) -> UserResult:
    """Clear another user's 2FA enrolment so they can enrol again.

    For a lost or replaced authenticator device. Requires write:settings,
    and cannot be aimed at yourself, removing your own 2FA goes through
    DELETE /users/me/totp/, which confirms with the current code.
    """
    return await use_case.execute(actor=actor, target_id=user_id)


# ── GET/DELETE /users/{user_id}/passkeys ─────────────────────────────


@router.get("/{user_id}/passkeys", response_model=list[PasskeyResult])
async def read_user_passkeys(
    user_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetUserPasskeys = Depends(get_user_passkeys_use_case),
) -> list[PasskeyResult]:
    """Another user's passkeys, newest first. Requires write:settings, your
    own are under GET /users/me/passkeys/."""
    return await use_case.execute(actor=actor, target_id=user_id)


@router.delete("/{user_id}/passkeys", response_model=RevokedCountResult)
async def reset_user_passkeys(
    user_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ResetUserPasskeys = Depends(get_reset_user_passkeys_use_case),
) -> RevokedCountResult:
    """Remove every passkey of another user, for a lost or stolen device.

    Requires write:settings and cannot be aimed at yourself. Like the 2FA
    reset it leaves the user's sessions alone, force-logout is its own
    action.
    """
    return RevokedCountResult(revoked=await use_case.execute(actor=actor, target_id=user_id))


# ── GET /users/{user_id}/avatar ──────────────────────────────────────


@router.get("/{user_id}/avatar")
async def read_user_avatar(
    user_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetUserAvatar = Depends(get_user_avatar_use_case),
) -> Response:
    """Stream a user's avatar image bytes. All authenticated users may read."""
    data, content_type = await use_case.execute(user_id=user_id)
    return Response(
        content=data, media_type=content_type, headers={"Cache-Control": "private, max-age=3600"}
    )


# ── POST /users/{user_id}/avatar ─────────────────────────────────────


@router.post(
    "/{user_id}/avatar",
    response_model=UserResponse,
    dependencies=[Depends(max_upload_size(AVATAR_MAX_BYTES))],
)
async def upload_user_avatar(
    user_id: int,
    file: UploadFile,
    actor: User = Depends(get_current_active_user),
    use_case: UploadUserAvatar = Depends(get_upload_user_avatar_use_case),
) -> UserResult:
    """Upload or replace a user's avatar image. Self, or requires write:settings."""
    data = await file.read()
    return await use_case.execute(
        actor=actor, user_id=user_id, data=data, content_type=file.content_type or ""
    )


# ── DELETE /users/{user_id}/avatar ───────────────────────────────────


@router.delete("/{user_id}/avatar", response_model=UserResponse)
async def delete_user_avatar(
    user_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteUserAvatar = Depends(get_delete_user_avatar_use_case),
) -> UserResult:
    """Remove a user's avatar. Self, or requires write:settings."""
    return await use_case.execute(actor=actor, user_id=user_id)


# ── PUT /users/{user_id} ──────────────────────────────────────────────


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UserUpdateRequest,
    request: Request,
    actor: User = Depends(get_current_active_user),  # see UserRules.assert_can_update
    use_case: UpdateUser = Depends(get_update_user_use_case),
) -> UserResult:
    """Update any user. Self, or requires write:settings. Changing one's own
    password needs `current_password` here too."""
    cmd = UpdateUserCommand(**body.model_dump(exclude_unset=True))
    return await use_case.execute(
        actor=actor, target_id=user_id, cmd=cmd, client_ip=client_ip(request)
    )
