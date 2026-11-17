"""Use case factories: the two interactive login steps, TOTP self-service, and
the acting user's own sessions and trusted devices.
"""

from collections.abc import Awaitable
from collections.abc import Callable

from fastapi import Depends

from src.modules.platform.adapters.inbound.api.auth_deps import TotpEnrolmentActor
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.auth_deps import get_totp_enrolment_actor
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_platform_settings_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_trusted_device_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_session_repo
from src.modules.platform.adapters.inbound.api.deps.services import get_login_attempt_tracker
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_ldap_authenticator
from src.modules.platform.adapters.inbound.api.deps.services import get_replay_guard
from src.modules.platform.adapters.inbound.api.deps.services import get_security_audit
from src.modules.platform.adapters.inbound.api.deps.users import get_password_confirmation
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.use_cases.auth.password_login import PasswordLogin
from src.modules.platform.application.use_cases.auth.totp_login import TotpLogin
from src.modules.platform.application.use_cases.session.manage_sessions import GetCurrentSession
from src.modules.platform.application.use_cases.session.manage_sessions import GetMySessions
from src.modules.platform.application.use_cases.session.manage_sessions import RevokeMyOtherSessions
from src.modules.platform.application.use_cases.session.manage_sessions import RevokeMySession
from src.modules.platform.application.use_cases.session.manage_trusted_devices import (
    GetMyTrustedDevices,
)
from src.modules.platform.application.use_cases.session.manage_trusted_devices import (
    RevokeAllMyTrustedDevices,
)
from src.modules.platform.application.use_cases.session.manage_trusted_devices import (
    RevokeMyTrustedDevice,
)
from src.modules.platform.application.use_cases.user.confirm_totp_enrollment import (
    ConfirmTOTPEnrollment,
)
from src.modules.platform.application.use_cases.user.disable_totp import DisableTOTP
from src.modules.platform.application.use_cases.user.enroll_totp import EnrollTOTP
from src.modules.platform.application.use_cases.user.identify_user_by_rfid import IdentifyUserByRfid
from src.modules.platform.application.use_cases.user.password_confirmation import (
    PasswordConfirmation,
)
from src.modules.platform.const import NAME
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.security.hashing import averify_hash
from src.modules.platform.infrastructure.security.totp import TOTP_REPLAY_TTL_SECONDS
from src.modules.platform.infrastructure.security.totp import generate_totp_secret
from src.modules.platform.infrastructure.security.totp import get_totp_provisioning_uri
from src.modules.platform.infrastructure.security.totp import verify_totp_once
from src.modules.platform.ports.outbound.ldap_authenticator_port import ILdapAuthenticator
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.replay_guard_port import IReplayGuard
from src.modules.platform.ports.outbound.repositories.trusted_device_repository import (
    ITrustedDeviceRepository,
)
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_password_login_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    attempts: ILoginAttemptTracker = Depends(get_login_attempt_tracker),
    ldap: ILdapAuthenticator | None = Depends(get_optional_ldap_authenticator),
    session_repo: IUserSessionRepository = Depends(get_user_session_repo),
    trusted_device_repo: ITrustedDeviceRepository = Depends(get_trusted_device_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> PasswordLogin:
    return PasswordLogin(
        user_repo=user_repo,
        settings_repo=settings_repo,
        attempts=attempts,
        ldap=ldap,
        session_repo=session_repo,
        trusted_device_repo=trusted_device_repo,
        uow=uow,
        verify_fn=averify_hash,
        audit=audit,
    )


def get_totp_login_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    attempts: ILoginAttemptTracker = Depends(get_login_attempt_tracker),
    replay_guard: IReplayGuard = Depends(get_replay_guard),
    session_repo: IUserSessionRepository = Depends(get_user_session_repo),
    trusted_device_repo: ITrustedDeviceRepository = Depends(get_trusted_device_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> TotpLogin:
    return TotpLogin(
        user_repo=user_repo,
        settings_repo=settings_repo,
        attempts=attempts,
        replay_guard=replay_guard,
        session_repo=session_repo,
        trusted_device_repo=trusted_device_repo,
        uow=uow,
        audit=audit,
    )


def get_identify_user_by_rfid_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> IdentifyUserByRfid:
    """The key surface's RFID lookup, which LDAP never takes part in."""
    return IdentifyUserByRfid(user_repo, settings_repo)


def _replay_protected_verify(
    user_id: int, replay_guard: IReplayGuard, flow: str
) -> Callable[[str, str], Awaitable[bool]]:
    """Builds the `verify` callable ConfirmTOTPEnrollment/DisableTOTP take,
    composing verify_totp_once with a replay claim scoped to this user and
    this flow, same replay protection as TotpLogin's code check, via the
    same verify_totp_once/IReplayGuard pair (see their docstrings). These
    two routes sit behind an authenticated session or setup token already,
    so unlike the TOTP login step they get no separate lockout throttle on
    top, replay protection alone is the gap this closes here.

    `flow` ("confirm" or "disable") keeps each call site's claimed counters
    separate from the other's and from TotpLogin's, a code used to confirm
    enrolment a moment ago must not spuriously block an unrelated disable
    (or login) landing in the same 30-second step.
    """

    async def _verify(secret: str, code: str) -> bool:
        return await verify_totp_once(
            secret,
            code,
            consume=lambda counter: replay_guard.consume_once(
                f"glados:totp:used:{flow}:{user_id}:{counter}", ttl_seconds=TOTP_REPLAY_TTL_SECONDS
            ),
        )

    return _verify


def get_enroll_totp_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    password_confirmation: PasswordConfirmation = Depends(get_password_confirmation),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> EnrollTOTP:
    return EnrollTOTP(
        user_repo=user_repo,
        secret_factory=generate_totp_secret,
        uri_factory=lambda secret, username: get_totp_provisioning_uri(secret, username, NAME),
        password_confirmation=password_confirmation,
        uow=uow,
    )


def get_confirm_totp_enrollment_use_case(
    actor: TotpEnrolmentActor = Depends(get_totp_enrolment_actor),
    user_repo: IUserRepository = Depends(get_user_repo),
    replay_guard: IReplayGuard = Depends(get_replay_guard),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> ConfirmTOTPEnrollment:
    """Depends on the enrolment actor, resolved once per request alongside
    the route's own, because the replay claim is scoped to that user."""
    return ConfirmTOTPEnrollment(
        user_repo=user_repo,
        verify=_replay_protected_verify(actor.user.id, replay_guard, flow="confirm"),
        uow=uow,
        audit=audit,
    )


def get_disable_totp_use_case(
    current_user: User = Depends(get_current_active_user),
    user_repo: IUserRepository = Depends(get_user_repo),
    replay_guard: IReplayGuard = Depends(get_replay_guard),
    trusted_device_repo: ITrustedDeviceRepository = Depends(get_trusted_device_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> DisableTOTP:
    """Depends on the acting user, resolved once per request alongside the
    route's own, because the replay claim is scoped to that user."""
    return DisableTOTP(
        user_repo=user_repo,
        verify=_replay_protected_verify(current_user.id, replay_guard, flow="disable"),
        trusted_device_repo=trusted_device_repo,
        uow=uow,
        audit=audit,
    )


def get_my_sessions_use_case(
    session_repo: IUserSessionRepository = Depends(get_user_session_repo),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetMySessions:
    return GetMySessions(session_repo, settings_repo)


def get_current_session_use_case(
    session_repo: IUserSessionRepository = Depends(get_user_session_repo),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
) -> GetCurrentSession:
    return GetCurrentSession(session_repo, settings_repo)


def get_revoke_my_other_sessions_use_case(
    session_repo: IUserSessionRepository = Depends(get_user_session_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> RevokeMyOtherSessions:
    return RevokeMyOtherSessions(session_repo, uow=uow, audit=audit)


def get_revoke_my_session_use_case(
    session_repo: IUserSessionRepository = Depends(get_user_session_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> RevokeMySession:
    return RevokeMySession(session_repo, uow=uow, audit=audit)


def get_my_trusted_devices_use_case(
    trusted_device_repo: ITrustedDeviceRepository = Depends(get_trusted_device_repo),
) -> GetMyTrustedDevices:
    return GetMyTrustedDevices(trusted_device_repo)


def get_revoke_all_my_trusted_devices_use_case(
    trusted_device_repo: ITrustedDeviceRepository = Depends(get_trusted_device_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RevokeAllMyTrustedDevices:
    return RevokeAllMyTrustedDevices(trusted_device_repo, uow=uow)


def get_revoke_my_trusted_device_use_case(
    trusted_device_repo: ITrustedDeviceRepository = Depends(get_trusted_device_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RevokeMyTrustedDevice:
    return RevokeMyTrustedDevice(trusted_device_repo, uow=uow)
