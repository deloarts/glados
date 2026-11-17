"""
TOTP 2FA management for the authenticated user (self-service).
Mounted at /api/v1/web/users/me/totp.
"""

from fastapi import Depends
from fastapi import Request
from fastapi import Response
from fastapi import status
from fastapi.routing import APIRouter
from pydantic import BaseModel

from src.modules.platform.adapters.inbound.api.auth_deps import TotpEnrolmentActor
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.auth_deps import get_totp_enrolment_actor
from src.modules.platform.adapters.inbound.api.deps.auth import get_confirm_totp_enrollment_use_case
from src.modules.platform.adapters.inbound.api.deps.auth import get_disable_totp_use_case
from src.modules.platform.adapters.inbound.api.deps.auth import get_enroll_totp_use_case
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_platform_settings_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_session_repo
from src.modules.platform.adapters.inbound.api.deps.services import get_security_audit
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.v1.auth.login_responses import client_ip
from src.modules.platform.application.services.login_session import issue_session_token
from src.modules.platform.application.services.login_session import read_session_limits
from src.modules.platform.application.services.login_session import session_cookie_max_age
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.use_cases.user.authenticate_user import AuthenticateUser
from src.modules.platform.application.use_cases.user.confirm_totp_enrollment import (
    ConfirmTOTPEnrollment,
)
from src.modules.platform.application.use_cases.user.disable_totp import DisableTOTP
from src.modules.platform.application.use_cases.user.enroll_totp import EnrollTOTP
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.security_event_type import LoginMethod
from src.modules.platform.domain.value_objects.security_event_type import SecurityEventType
from src.modules.platform.infrastructure.security.session_cookie import set_session_cookie
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

router = APIRouter()


class TOTPEnrollResponse(ResponseModel):
    secret: str
    provisioning_uri: str


class TOTPCodeRequest(BaseModel):
    totp_code: str


class TOTPEnrollRequest(BaseModel):
    """The current password, required when enrolling from a session. A
    user forced to enrol at sign-in sends no body."""

    password: str | None = None


class TOTPConfirmResponse(ResponseModel):
    """`access_token` is present only for enrolment forced at login: that
    user has no session yet, and the code they just entered already proves
    possession of the secret, so making them log in again to type a second
    code would be pure friction. Voluntary enrolment already has a
    session and gets `detail` alone, exactly as before."""

    detail: str
    access_token: str | None = None
    token_type: str | None = None


@router.post("/enroll", response_model=TOTPEnrollResponse, status_code=status.HTTP_200_OK)
async def enroll_totp(
    request: Request,
    body: TOTPEnrollRequest | None = None,
    actor: TotpEnrolmentActor = Depends(get_totp_enrolment_actor),
    use_case: EnrollTOTP = Depends(get_enroll_totp_use_case),
) -> TOTPEnrollResponse:
    """Generate a new TOTP secret and return it with a provisioning URI for QR code scanning.

    Accepts a normal session or a totp_setup token, so a user forced to
    enrol at login can reach it. A session caller confirms the current
    password: a missing one answers 400 CurrentPasswordRequiredError, a
    wrong one 400 PasswordConfirmationFailedError, counted toward the login
    throttle. Re-enrolling overwrites any previous unconfirmed secret, so
    an abandoned attempt cannot strand the user.
    """
    result = await use_case.execute(
        actor.user.id,
        password=body.password if body else None,
        proven_at_sign_in=actor.via_setup_token,
        client_ip=client_ip(request),
    )
    return TOTPEnrollResponse(secret=result.secret, provisioning_uri=result.provisioning_uri)


@router.post("/confirm", response_model=TOTPConfirmResponse, status_code=status.HTTP_200_OK)
async def confirm_totp(
    body: TOTPCodeRequest,
    request: Request,
    response: Response,
    actor: TotpEnrolmentActor = Depends(get_totp_enrolment_actor),
    use_case: ConfirmTOTPEnrollment = Depends(get_confirm_totp_enrollment_use_case),
    user_repo: IUserRepository = Depends(get_user_repo),
    session_repo: IUserSessionRepository = Depends(get_user_session_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    audit: SecurityAudit = Depends(get_security_audit),
) -> TOTPConfirmResponse:
    """Confirm TOTP enrollment by verifying the first code. Activates 2FA on the account."""
    await use_case.execute(actor.user.id, body.totp_code)

    if not actor.via_setup_token:
        return TOTPConfirmResponse(detail="2FA enabled")

    # Forced enrolment: the user arrived with a setup token and no session.
    # Re-read the user, ConfirmTOTPEnrollment has just saved it, so the
    # session carries the current token_version.
    enrolled = await user_repo.get_by_id(actor.user.id)
    assert enrolled is not None  # just confirmed above
    await AuthenticateUser.complete_login(user_repo, enrolled)
    # Committed with the session below, like every other completed login.
    await audit.record(
        SecurityEventType.LOGIN,
        actor=enrolled,
        target_user=enrolled,
        detail={"method": LoginMethod.TOTP_ENROLMENT.value},
    )

    session_token = await issue_session_token(
        session_repo,
        uow,
        enrolled,
        user_agent=request.headers.get("user-agent"),
        client_ip=request.client.host if request.client else None,
    )
    limits = await read_session_limits(settings_repo)
    set_session_cookie(
        response, session_token, session_cookie_max_age(enrolled, limits.max_lifetime_days)
    )
    return TOTPConfirmResponse(
        detail="2FA enabled", access_token=session_token, token_type="bearer"
    )


@router.delete("/", response_model=dict, status_code=status.HTTP_200_OK)
async def disable_totp(
    body: TOTPCodeRequest,
    current_user: User = Depends(get_current_active_user),
    use_case: DisableTOTP = Depends(get_disable_totp_use_case),
) -> dict[str, str]:
    """Disable 2FA after verifying a valid TOTP code."""
    await use_case.execute(current_user.id, body.totp_code)
    return {"detail": "2FA disabled"}
