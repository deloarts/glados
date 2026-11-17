"""
Unit coverage for EnrollTOTP, ConfirmTOTPEnrollment and DisableTOTP. Neither
of the last two logs an invalid code itself (see both modules): the request
that reaches
either use case is already authenticated as `user`, so
domain_error_handler's own log line for InvalidTOTPCodeError already
carries the same username/id via ContextFilter's user_ctx. These tests pin
both halves: the use cases raise and succeed as they should, and they do
not log.
"""

from typing import Any

import pytest

from src.modules.platform.application.use_cases.user.confirm_totp_enrollment import (
    ConfirmTOTPEnrollment,
)
from src.modules.platform.application.use_cases.user.disable_totp import DisableTOTP
from src.modules.platform.application.use_cases.user.enroll_totp import EnrollTOTP
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import CurrentPasswordRequiredError
from src.modules.platform.domain.exceptions import InvalidTOTPCodeError
from src.modules.platform.domain.exceptions import PasswordConfirmationFailedError
from src.modules.platform.domain.exceptions import TOTPAlreadyEnabledError
from src.modules.platform.domain.exceptions import TOTPNotEnabledError
from src.modules.platform.domain.exceptions import UserNotFoundError
from tests import factories
from tests.unit.fakes import FakeUnitOfWork


def make_user(*, totp_secret: str | None = "SECRET", **overrides: Any) -> User:
    """A user with a TOTP secret on file, the state enrolment and verification start from."""
    return factories.make_user(totp_secret=totp_secret, **overrides)


async def _accept(secret: str, code: str) -> bool:
    return True


async def _reject(secret: str, code: str) -> bool:
    return False


class FakeUserRepository:
    def __init__(self, users: list[User]) -> None:
        self._users = {u.id: u for u in users}

    async def get_by_id(self, id: int) -> User | None:
        return self._users.get(id)

    async def save(self, user: User) -> User:
        self._users[user.id] = user
        return user


class FakeTrustedDeviceRepository:
    def __init__(self) -> None:
        self.revoked_for_user_ids: list[int] = []

    async def revoke_all_for_user(self, user_id: int) -> int:
        self.revoked_for_user_ids.append(user_id)
        return 0


# ── EnrollTOTP ───────────────────────────────────────────────────────────


class FakePasswordConfirmation:
    """Accepts only `PASSWORD` and records every password it was asked to
    confirm."""

    PASSWORD = "right-password"

    def __init__(self) -> None:
        self.asked: list[str] = []

    async def confirm(self, actor: User, password: str, *, client_ip: str | None) -> User:
        self.asked.append(password)
        if password != self.PASSWORD:
            raise PasswordConfirmationFailedError("The password is not correct.")
        return actor


def _enroll(
    repo: FakeUserRepository, confirmation: FakePasswordConfirmation | None = None
) -> EnrollTOTP:
    return EnrollTOTP(
        repo,
        secret_factory=lambda: "NEWSECRET",
        uri_factory=lambda secret, username: f"otpauth://totp/{username}?secret={secret}",
        password_confirmation=confirmation or FakePasswordConfirmation(),  # type: ignore[arg-type]
        uow=FakeUnitOfWork(),
    )


class TestEnrollTOTP:
    async def test_a_new_secret_is_stored_and_2fa_stays_off(self):
        user = make_user(totp_secret=None, totp_enabled=False)
        repo = FakeUserRepository([user])

        result = await _enroll(repo).execute(user_id=1, password=None, proven_at_sign_in=True)

        stored = await repo.get_by_id(1)
        assert result.secret == "NEWSECRET"
        assert stored.totp_secret == "NEWSECRET"
        assert stored.totp_enabled is False

    async def test_an_unconfirmed_secret_is_replaced(self):
        user = make_user(totp_secret="ABANDONED", totp_enabled=False)
        repo = FakeUserRepository([user])

        await _enroll(repo).execute(user_id=1, password=None, proven_at_sign_in=True)

        assert (await repo.get_by_id(1)).totp_secret == "NEWSECRET"

    async def test_an_account_with_2fa_on_keeps_its_secret(self):
        user = make_user(totp_secret="ACTIVE", totp_enabled=True)
        repo = FakeUserRepository([user])

        with pytest.raises(TOTPAlreadyEnabledError):
            await _enroll(repo).execute(user_id=1, password=None, proven_at_sign_in=True)

        assert (await repo.get_by_id(1)).totp_secret == "ACTIVE"

    async def test_a_session_enrolment_confirms_the_password(self):
        user = make_user(totp_secret=None, totp_enabled=False)
        repo = FakeUserRepository([user])
        confirmation = FakePasswordConfirmation()

        result = await _enroll(repo, confirmation).execute(
            user_id=1, password=FakePasswordConfirmation.PASSWORD, proven_at_sign_in=False
        )

        assert confirmation.asked == [FakePasswordConfirmation.PASSWORD]
        assert result.secret == "NEWSECRET"

    async def test_a_session_enrolment_without_a_password_is_refused(self):
        user = make_user(totp_secret=None, totp_enabled=False)
        repo = FakeUserRepository([user])
        confirmation = FakePasswordConfirmation()

        with pytest.raises(CurrentPasswordRequiredError):
            await _enroll(repo, confirmation).execute(
                user_id=1, password=None, proven_at_sign_in=False
            )

        assert confirmation.asked == []
        assert (await repo.get_by_id(1)).totp_secret is None

    async def test_a_session_enrolment_with_a_wrong_password_stores_nothing(self):
        user = make_user(totp_secret=None, totp_enabled=False)
        repo = FakeUserRepository([user])

        with pytest.raises(PasswordConfirmationFailedError):
            await _enroll(repo).execute(user_id=1, password="wrong", proven_at_sign_in=False)

        assert (await repo.get_by_id(1)).totp_secret is None

    async def test_a_forced_enrolment_is_not_asked_for_the_password(self):
        user = make_user(totp_secret=None, totp_enabled=False)
        repo = FakeUserRepository([user])
        confirmation = FakePasswordConfirmation()

        await _enroll(repo, confirmation).execute(user_id=1, password=None, proven_at_sign_in=True)

        assert confirmation.asked == []


# ── ConfirmTOTPEnrollment ────────────────────────────────────────────────


class TestConfirmTOTPEnrollment:
    async def test_a_correct_code_activates_2fa(self):
        user = make_user()
        repo = FakeUserRepository([user])
        use_case = ConfirmTOTPEnrollment(repo, verify=_accept, uow=FakeUnitOfWork())

        await use_case.execute(user_id=1, totp_code="123456")

        assert (await repo.get_by_id(1)).totp_enabled is True

    async def test_an_incorrect_code_raises_and_leaves_2fa_disabled(self):
        user = make_user()
        repo = FakeUserRepository([user])
        use_case = ConfirmTOTPEnrollment(repo, verify=_reject, uow=FakeUnitOfWork())

        with pytest.raises(InvalidTOTPCodeError):
            await use_case.execute(user_id=1, totp_code="000000")

        assert (await repo.get_by_id(1)).totp_enabled is False

    async def test_an_incorrect_code_is_not_logged_by_the_use_case_itself(self, glados_caplog):
        """domain_error_handler is the sole remaining log line for
        this event (InvalidTOTPCodeError isn't in _SELF_LOGGED). This use
        case must not add a second one."""
        user = make_user()
        repo = FakeUserRepository([user])
        use_case = ConfirmTOTPEnrollment(repo, verify=_reject, uow=FakeUnitOfWork())

        with pytest.raises(InvalidTOTPCodeError):
            await use_case.execute(user_id=1, totp_code="000000")

        assert glados_caplog.records == []

    async def test_no_user_raises_user_not_found(self):
        repo = FakeUserRepository([])
        use_case = ConfirmTOTPEnrollment(repo, verify=_accept, uow=FakeUnitOfWork())

        with pytest.raises(UserNotFoundError):
            await use_case.execute(user_id=999, totp_code="123456")

    async def test_no_enrollment_in_progress_raises(self):
        user = make_user(totp_secret=None)
        repo = FakeUserRepository([user])
        use_case = ConfirmTOTPEnrollment(repo, verify=_accept, uow=FakeUnitOfWork())

        with pytest.raises(TOTPNotEnabledError):
            await use_case.execute(user_id=1, totp_code="123456")


# ── DisableTOTP ──────────────────────────────────────────────────────────


class TestDisableTOTP:
    async def test_a_correct_code_disables_2fa_and_revokes_trusted_devices(self):
        user = make_user(totp_enabled=True)
        repo = FakeUserRepository([user])
        trusted_devices = FakeTrustedDeviceRepository()
        use_case = DisableTOTP(
            repo, verify=_accept, trusted_device_repo=trusted_devices, uow=FakeUnitOfWork()
        )

        await use_case.execute(user_id=1, totp_code="123456")

        saved = await repo.get_by_id(1)
        assert saved.totp_enabled is False
        assert saved.totp_secret is None
        assert trusted_devices.revoked_for_user_ids == [1]

    async def test_an_incorrect_code_raises_and_leaves_2fa_enabled(self):
        user = make_user(totp_enabled=True)
        repo = FakeUserRepository([user])
        trusted_devices = FakeTrustedDeviceRepository()
        use_case = DisableTOTP(
            repo, verify=_reject, trusted_device_repo=trusted_devices, uow=FakeUnitOfWork()
        )

        with pytest.raises(InvalidTOTPCodeError):
            await use_case.execute(user_id=1, totp_code="000000")

        assert (await repo.get_by_id(1)).totp_enabled is True
        assert trusted_devices.revoked_for_user_ids == []

    async def test_an_incorrect_code_is_not_logged_by_the_use_case_itself(self, glados_caplog):
        user = make_user(totp_enabled=True)
        repo = FakeUserRepository([user])
        trusted_devices = FakeTrustedDeviceRepository()
        use_case = DisableTOTP(
            repo, verify=_reject, trusted_device_repo=trusted_devices, uow=FakeUnitOfWork()
        )

        with pytest.raises(InvalidTOTPCodeError):
            await use_case.execute(user_id=1, totp_code="000000")

        assert glados_caplog.records == []

    async def test_no_user_raises_user_not_found(self):
        repo = FakeUserRepository([])
        trusted_devices = FakeTrustedDeviceRepository()
        use_case = DisableTOTP(
            repo, verify=_accept, trusted_device_repo=trusted_devices, uow=FakeUnitOfWork()
        )

        with pytest.raises(UserNotFoundError):
            await use_case.execute(user_id=999, totp_code="123456")

    async def test_2fa_not_enabled_raises(self):
        user = make_user(totp_enabled=False)
        repo = FakeUserRepository([user])
        trusted_devices = FakeTrustedDeviceRepository()
        use_case = DisableTOTP(
            repo, verify=_accept, trusted_device_repo=trusted_devices, uow=FakeUnitOfWork()
        )

        with pytest.raises(TOTPNotEnabledError):
            await use_case.execute(user_id=1, totp_code="123456")
