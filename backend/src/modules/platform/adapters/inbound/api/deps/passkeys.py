"""Use case factories for passkeys: the passkey login, registering and
removing the acting user's own passkeys, and the administrative reset.
"""

from fastapi import Depends

from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_passkey_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_platform_settings_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_repo
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_session_repo
from src.modules.platform.adapters.inbound.api.deps.services import get_login_attempt_tracker
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_ldap_authenticator
from src.modules.platform.adapters.inbound.api.deps.services import get_replay_guard
from src.modules.platform.adapters.inbound.api.deps.services import get_security_audit
from src.modules.platform.application.services.security_audit import SecurityAudit
from src.modules.platform.application.use_cases.auth.passkey_login import BeginPasskeyLogin
from src.modules.platform.application.use_cases.auth.passkey_login import PasskeyLogin
from src.modules.platform.application.use_cases.passkey.manage_passkeys import DeleteAllMyPasskeys
from src.modules.platform.application.use_cases.passkey.manage_passkeys import DeleteMyPasskey
from src.modules.platform.application.use_cases.passkey.manage_passkeys import GetMyPasskeys
from src.modules.platform.application.use_cases.passkey.manage_passkeys import GetUserPasskeys
from src.modules.platform.application.use_cases.passkey.manage_passkeys import RenameMyPasskey
from src.modules.platform.application.use_cases.passkey.manage_passkeys import ResetUserPasskeys
from src.modules.platform.application.use_cases.passkey.register_passkey import (
    BeginPasskeyRegistration,
)
from src.modules.platform.application.use_cases.passkey.register_passkey import (
    FinishPasskeyRegistration,
)
from src.modules.platform.infrastructure.security.hashing import averify_hash
from src.modules.platform.infrastructure.security.webauthn import default_passkey_verifier
from src.modules.platform.ports.outbound.ldap_authenticator_port import ILdapAuthenticator
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.passkey_verifier_port import IPasskeyVerifier
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.replay_guard_port import IReplayGuard
from src.modules.platform.ports.outbound.repositories.passkey_repository import IPasskeyRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.repositories.user_session_repository import (
    IUserSessionRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_passkey_verifier() -> IPasskeyVerifier:
    return default_passkey_verifier()


def get_begin_passkey_login_use_case(
    verifier: IPasskeyVerifier = Depends(get_passkey_verifier),
) -> BeginPasskeyLogin:
    return BeginPasskeyLogin(verifier)


def get_passkey_login_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    attempts: ILoginAttemptTracker = Depends(get_login_attempt_tracker),
    session_repo: IUserSessionRepository = Depends(get_user_session_repo),
    passkey_repo: IPasskeyRepository = Depends(get_passkey_repo),
    replay_guard: IReplayGuard = Depends(get_replay_guard),
    verifier: IPasskeyVerifier = Depends(get_passkey_verifier),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> PasskeyLogin:
    return PasskeyLogin(
        user_repo=user_repo,
        settings_repo=settings_repo,
        attempts=attempts,
        session_repo=session_repo,
        passkey_repo=passkey_repo,
        replay_guard=replay_guard,
        verifier=verifier,
        uow=uow,
        audit=audit,
    )


def get_begin_passkey_registration_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    passkey_repo: IPasskeyRepository = Depends(get_passkey_repo),
    settings_repo: IPlatformSettingsRepository = Depends(get_platform_settings_repo),
    attempts: ILoginAttemptTracker = Depends(get_login_attempt_tracker),
    ldap: ILdapAuthenticator | None = Depends(get_optional_ldap_authenticator),
    verifier: IPasskeyVerifier = Depends(get_passkey_verifier),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> BeginPasskeyRegistration:
    return BeginPasskeyRegistration(
        user_repo=user_repo,
        passkey_repo=passkey_repo,
        settings_repo=settings_repo,
        attempts=attempts,
        ldap=ldap,
        verifier=verifier,
        uow=uow,
        verify_fn=averify_hash,
        audit=audit,
    )


def get_finish_passkey_registration_use_case(
    passkey_repo: IPasskeyRepository = Depends(get_passkey_repo),
    replay_guard: IReplayGuard = Depends(get_replay_guard),
    verifier: IPasskeyVerifier = Depends(get_passkey_verifier),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> FinishPasskeyRegistration:
    return FinishPasskeyRegistration(
        passkey_repo=passkey_repo,
        replay_guard=replay_guard,
        verifier=verifier,
        uow=uow,
        audit=audit,
    )


def get_my_passkeys_use_case(
    passkey_repo: IPasskeyRepository = Depends(get_passkey_repo),
) -> GetMyPasskeys:
    return GetMyPasskeys(passkey_repo)


def get_rename_my_passkey_use_case(
    passkey_repo: IPasskeyRepository = Depends(get_passkey_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RenameMyPasskey:
    return RenameMyPasskey(passkey_repo, uow=uow)


def get_delete_my_passkey_use_case(
    passkey_repo: IPasskeyRepository = Depends(get_passkey_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> DeleteMyPasskey:
    return DeleteMyPasskey(passkey_repo, uow=uow, audit=audit)


def get_delete_all_my_passkeys_use_case(
    passkey_repo: IPasskeyRepository = Depends(get_passkey_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> DeleteAllMyPasskeys:
    return DeleteAllMyPasskeys(passkey_repo, uow=uow, audit=audit)


def get_user_passkeys_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    passkey_repo: IPasskeyRepository = Depends(get_passkey_repo),
) -> GetUserPasskeys:
    return GetUserPasskeys(user_repo, passkey_repo)


def get_reset_user_passkeys_use_case(
    user_repo: IUserRepository = Depends(get_user_repo),
    passkey_repo: IPasskeyRepository = Depends(get_passkey_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    audit: SecurityAudit = Depends(get_security_audit),
) -> ResetUserPasskeys:
    return ResetUserPasskeys(user_repo, passkey_repo, uow=uow, audit=audit)
