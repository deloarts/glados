"""Stores the actor's own time tracking credentials after the time tracking
service verified them.

Order matters, every check before the first request to the service: time
tracking is available, the actor is a personal account, the current consent
text was confirmed, a password is present where the stored credentials
cannot be re-verified, the user name is not linked to another Glados user,
and the actor is not locked out after failed checks. Only then are user
name and password sealed for the confirmed credential key and handed to the
service, which signs in and checks the rights. A rejected sign-in counts
towards the lockout and stores nothing.

On success the row is written with the user name (encrypted by the column
type), the sealed value, the binding the service returned and the key id it
was sealed for, a fresh consent stamp and no auth-failed mark. Glados never
holds the password beyond this request, and the stored value only the
service can open. Employee name and rights are returned, not stored.

An omitted password re-verifies the stored sealed value, which only works
for the same user name and while that value is still usable.
"""

from collections.abc import Callable
from datetime import datetime

from src.modules.operations.application.dto.time_tracking_dto import (
    SaveTimeTrackingCredentialsCommand,
)
from src.modules.operations.application.dto.time_tracking_dto import TimeTrackingAccountResult
from src.modules.operations.application.mappers.time_tracking_mapper import TimeTrackingMapper
from src.modules.operations.application.services.time_tracking_access import (
    assert_verify_not_locked,
)
from src.modules.operations.application.services.time_tracking_access import (
    load_time_tracking_setup,
)
from src.modules.operations.application.services.time_tracking_access import record_verify_failure
from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    AdminTimeTrackingSettings,
)
from src.modules.operations.domain.entities.user_time_tracking_credentials import (
    UserTimeTrackingCredentials,
)
from src.modules.operations.domain.errors import TimeTrackingAuthenticationFailedError
from src.modules.operations.domain.errors import TimeTrackingCredentialsMissingError
from src.modules.operations.domain.errors import TimeTrackingUserAlreadyLinkedError
from src.modules.operations.domain.services.time_tracking_rules import TIME_TRACKING_CONSENT_VERSION
from src.modules.operations.domain.services.time_tracking_rules import CredentialsInvalidReason
from src.modules.operations.domain.services.time_tracking_rules import assert_consent_current
from src.modules.operations.domain.services.time_tracking_rules import credentials_invalid_reason
from src.modules.operations.domain.services.time_tracking_rules import fingerprint_subject
from src.modules.operations.infrastructure.security.time_tracking_fingerprint import (
    time_tracking_fingerprint,
)
from src.modules.operations.infrastructure.security.time_tracking_fingerprint import (
    time_tracking_fingerprint_key_id,
)
from src.modules.operations.infrastructure.security.time_tracking_sealer import seal_credentials
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.repositories.user_time_tracking_credentials_repository import (
    IUserTimeTrackingCredentialsRepository,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    ITimeTrackingProviderFactory,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.login_attempt_tracker_port import ILoginAttemptTracker
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


def _reusable_sealed(
    existing: UserTimeTrackingCredentials | None,
    user: str,
    settings: AdminTimeTrackingSettings,
) -> str | None:
    """The stored sealed value, when it belongs to the same user name and is
    still usable apart from the consent, which this save renews."""
    if existing is None or existing.time_tracking_user is None:
        return None
    if fingerprint_subject(existing.time_tracking_user) != fingerprint_subject(user):
        return None
    reason = credentials_invalid_reason(existing, current_key_id=settings.credential_key_id)
    if reason not in (None, CredentialsInvalidReason.CONSENT_OUTDATED):
        return None
    return existing.time_tracking_sealed_credentials


class SaveMyTimeTrackingCredentials:
    def __init__(
        self,
        settings_repo: IOperationsSettingsRepository,
        credentials_repo: IUserTimeTrackingCredentialsRepository,
        provider_factory: ITimeTrackingProviderFactory,
        rate_tracker: ILoginAttemptTracker,
        *,
        uow: IUnitOfWork,
        clock: Callable[[], datetime] = now_utc,
    ) -> None:
        self._settings = settings_repo
        self._credentials = credentials_repo
        self._provider_factory = provider_factory
        self._rate_tracker = rate_tracker
        self._uow = uow
        self._clock = clock

    async def execute(
        self, actor: User, cmd: SaveTimeTrackingCredentialsCommand
    ) -> TimeTrackingAccountResult:
        setup = await load_time_tracking_setup(actor, self._settings)
        settings = setup.settings
        assert settings.credential_public_key and settings.credential_key_id
        assert_consent_current(cmd.time_tracking_consent_version)

        existing = await self._credentials.get_by_user(actor.id)
        if cmd.time_tracking_password is not None:
            sealed = seal_credentials(
                {
                    "user": cmd.time_tracking_user,
                    "password": cmd.time_tracking_password.get_secret_value(),
                },
                settings.credential_public_key,
            )
        else:
            reusable = _reusable_sealed(existing, cmd.time_tracking_user, settings)
            if reusable is None:
                raise TimeTrackingCredentialsMissingError(
                    "Enter your time tracking password to save the credentials."
                )
            sealed = reusable

        fingerprint = time_tracking_fingerprint(fingerprint_subject(cmd.time_tracking_user))
        if await self._credentials.is_fingerprint_taken_by_other_user(fingerprint, actor.id):
            raise TimeTrackingUserAlreadyLinkedError(
                "This time tracking user is already linked to another Glados account."
            )
        await assert_verify_not_locked(self._rate_tracker, actor.id)

        # Nothing is written before the service accepted the credentials;
        # ending the read transaction hands the connection back to the pool
        # meanwhile.
        await self._uow.commit()
        provider = self._provider_factory(setup.connection)
        try:
            verification = await provider.verify(sealed)
        except TimeTrackingAuthenticationFailedError:
            await record_verify_failure(self._rate_tracker, actor.id)
            raise

        now = self._clock()
        saved = await self._credentials.save(
            UserTimeTrackingCredentials(
                id=existing.id if existing else 0,
                user_id=actor.id,
                time_tracking_user=cmd.time_tracking_user,
                time_tracking_sealed_credentials=sealed,
                time_tracking_binding=verification.binding,
                time_tracking_credential_key_id=settings.credential_key_id,
                time_tracking_user_fingerprint=fingerprint,
                time_tracking_user_fingerprint_key_id=time_tracking_fingerprint_key_id(),
                time_tracking_auth_failed_at=None,
                time_tracking_consent_at=now,
                time_tracking_consent_version=TIME_TRACKING_CONSENT_VERSION,
                created_at=existing.created_at if existing else now,
                updated_at=now,
            )
        )
        await self._uow.commit()

        log.info("Time tracking credentials %s.", "changed" if existing else "set")
        return TimeTrackingMapper.account_to_result(
            settings,
            saved,
            employee_name=verification.employee_name,
            rights=verification.rights,
        )
