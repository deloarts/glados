"""
Unit coverage for PasswordLogin and TotpLogin, one test per outcome and per
refusal. Besides the outcome itself the tests pin the order of the checks,
because that order is what keeps the logins from leaking account state:
the lockout gate before the credential, failures counted for unknown names,
and the setting-dependent refusals only after the credential was proven.
"""

from typing import Any

import pyotp
import pytest

from src.modules.platform.application.dto.login_dto import PasswordLoginCommand
from src.modules.platform.application.dto.login_dto import SessionIssued
from src.modules.platform.application.dto.login_dto import TotpChallengeIssued
from src.modules.platform.application.dto.login_dto import TotpLoginCommand
from src.modules.platform.application.dto.login_dto import TotpSetupRequired
from src.modules.platform.application.use_cases.auth.password_login import PasswordLogin
from src.modules.platform.application.use_cases.auth.totp_login import TotpLogin
from src.modules.platform.domain.entities.admin_settings.auth import AdminAuthSettings
from src.modules.platform.domain.entities.admin_settings.maintenance import AdminMaintenanceSettings
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.entities.trusted_device import TrustedDevice
from src.modules.platform.domain.entities.trusted_device import make_trusted_device
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.entities.user_session import UserSession
from src.modules.platform.domain.exceptions import CredentialsUnverifiableError
from src.modules.platform.domain.exceptions import InactiveUserError
from src.modules.platform.domain.exceptions import InvalidTOTPCodeError
from src.modules.platform.domain.exceptions import LdapUnavailableError
from src.modules.platform.domain.exceptions import LocalLoginDisabledError
from src.modules.platform.domain.exceptions import LoginLockedError
from src.modules.platform.domain.exceptions import MaintenanceModeError
from src.modules.platform.domain.exceptions import TOTPChallengeInvalidError
from src.modules.platform.domain.exceptions import TOTPNotEnabledError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.login_policy import TOTP_LOCK_SECONDS
from src.modules.platform.domain.services.login_policy import TOTP_MAX_ATTEMPTS
from src.modules.platform.domain.services.session_rules import DEFAULT_SESSION_MAX_LIFETIME_DAYS
from src.modules.platform.domain.services.session_rules import SYSTEM_USER_SESSION_LIFETIME_MINUTES
from src.modules.platform.domain.value_objects import token_scope
from src.modules.platform.domain.value_objects.auth_provider import AuthProvider
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.security.token import create_partial_token
from src.modules.platform.infrastructure.security.token import create_setup_token
from src.modules.platform.infrastructure.security.token import get_token_payload
from src.modules.platform.infrastructure.security.totp import generate_totp_secret
from src.modules.platform.infrastructure.security.trusted_device import hash_trusted_device
from tests import factories
from tests.unit.fakes import FakeUnitOfWork

PASSWORD = "right-password"
CLIENT_IP = "10.0.0.7"
USER_AGENT = "pytest-browser"

# The cookie lives as long as the session may: the shipped absolute lifetime.
SESSION_COOKIE_MAX_AGE_SECONDS = DEFAULT_SESSION_MAX_LIFETIME_DAYS * 24 * 60 * 60

# The login throttle's scopes for alice signing in from CLIENT_IP, see
# application/services/login_throttle.py.
PAIR_KEY = f"alice|{CLIENT_IP}"
DELAY_KEY = "delay:alice"
SUCCESS_RESETS = ["alice", DELAY_KEY, PAIR_KEY]

# ── fakes ─────────────────────────────────────────────────────────────


class FakeUserRepository:
    def __init__(self, users: list[User]) -> None:
        self.users = {u.id: u for u in users}
        self.saved: list[User] = []

    async def get_by_username_or_email(self, identifier: str) -> User | None:
        wanted = identifier.strip().lower()
        for user in self.users.values():
            if wanted in (user.username.lower(), (user.email or "").lower()):
                return user
        return None

    async def get_by_id(self, id: int) -> User | None:
        return self.users.get(id)

    async def save(self, user: User) -> User:
        self.saved.append(user)
        self.users[user.id] = user
        return user


class FakeSettingsRepository:
    def __init__(
        self,
        *,
        security: AdminSecuritySettings | None = None,
        maintenance: AdminMaintenanceSettings | None = None,
        auth: AdminAuthSettings | None = None,
        auth_missing: bool = False,
    ) -> None:
        self.security = security or make_security()
        self.maintenance = maintenance or AdminMaintenanceSettings(
            id=1, enabled=False, message=None
        )
        self.auth = auth or make_auth(ldap_enabled=False)
        self.auth_missing = auth_missing
        self.maintenance_reads = 0

    async def get_security(self) -> AdminSecuritySettings:
        return self.security

    async def get_auth(self) -> AdminAuthSettings:
        if self.auth_missing:
            raise RuntimeError("admin_auth_settings row missing")
        return self.auth

    async def get_maintenance(self) -> AdminMaintenanceSettings:
        self.maintenance_reads += 1
        return self.maintenance


class FakeAttemptTracker:
    def __init__(self) -> None:
        self.failures: dict[str, int] = {}
        self.locks: dict[str, int] = {}
        self.resets: list[str] = []

    async def record_failure(self, key: str) -> int:
        self.failures[key] = self.failures.get(key, 0) + 1
        return self.failures[key]

    async def reset(self, key: str) -> None:
        self.resets.append(key)
        self.failures.pop(key, None)
        self.locks.pop(key, None)

    async def lock(self, key: str, seconds: int) -> None:
        self.locks[key] = seconds
        self.failures.pop(key, None)

    async def lock_ttl(self, key: str) -> int:
        return self.locks.get(key, 0)

    async def clear_all(self) -> int:
        return 0


class FakeReplayGuard:
    def __init__(self) -> None:
        self.claimed: set[str] = set()

    async def consume_once(self, key: str, ttl_seconds: int) -> bool:
        if key in self.claimed:
            return False
        self.claimed.add(key)
        return True


class FakeSessionRepository:
    def __init__(self) -> None:
        self.saved: list[UserSession] = []

    async def save(self, session: UserSession) -> UserSession:
        session.id = len(self.saved) + 1
        self.saved.append(session)
        return session


class FakeTrustedDeviceRepository:
    def __init__(self, devices: list[TrustedDevice] | None = None) -> None:
        self.devices = list(devices or [])
        self.saved: list[TrustedDevice] = []
        self.lookups = 0

    async def get_by_token_hash(self, token_hash: str) -> TrustedDevice | None:
        self.lookups += 1
        return next((d for d in self.devices if d.token_hash == token_hash), None)

    async def save(self, device: TrustedDevice) -> TrustedDevice:
        self.saved.append(device)
        return device


class FakeDirectory:
    def __init__(self, *, accept: bool = True, unreachable: bool = False) -> None:
        self.accept = accept
        self.unreachable = unreachable
        self.binds = 0

    async def authenticate(self, username: str, password: str) -> bool:
        self.binds += 1
        if self.unreachable:
            raise LdapUnavailableError("directory down")
        return self.accept


async def _verify_password(password: str, hashed: str) -> bool:
    return password == PASSWORD


# ── builders ──────────────────────────────────────────────────────────


def make_security(**overrides: Any) -> AdminSecuritySettings:
    fields: dict[str, Any] = {
        "id": 1,
        "enforce_totp": False,
        "allow_rfid_login": True,
        "allow_local_login": True,
        "enable_api_key_auth": False,
        "min_password_length": 8,
        "session_timeout_minutes": 0,
        "totp_trusted_device_days": 0,
        "max_login_attempts": 0,
        "lockout_duration_minutes": 15,
        "token_max_lifetime_days": 3650,
    }
    fields.update(overrides)
    return AdminSecuritySettings(**fields)


def make_auth(*, ldap_enabled: bool) -> AdminAuthSettings:
    return AdminAuthSettings(
        id=1,
        ldap_enabled=ldap_enabled,
        ldap_host="dc.example.com",
        ldap_port=636,
        ldap_use_ssl=True,
        ldap_start_tls=False,
        ldap_verify_certificate=True,
        ldap_domain="EXAMPLE",
        ldap_timeout_seconds=5,
    )


def make_user(**overrides: Any) -> User:
    fields: dict[str, Any] = {"id": 7, "username": "alice", "token_version": 0}
    fields.update(overrides)
    return factories.make_user(**fields)


class Harness:
    """Every port the two use cases take, seeded per test."""

    def __init__(
        self,
        users: list[User],
        *,
        settings: FakeSettingsRepository | None = None,
        devices: list[TrustedDevice] | None = None,
        ldap: FakeDirectory | None = None,
    ) -> None:
        self.users = FakeUserRepository(users)
        self.settings = settings or FakeSettingsRepository()
        self.attempts = FakeAttemptTracker()
        self.replay_guard = FakeReplayGuard()
        self.sessions = FakeSessionRepository()
        self.devices = FakeTrustedDeviceRepository(devices)
        self.uow = FakeUnitOfWork()
        self.ldap = ldap

    def password_login(self) -> PasswordLogin:
        return PasswordLogin(
            user_repo=self.users,
            settings_repo=self.settings,
            attempts=self.attempts,
            ldap=self.ldap,
            session_repo=self.sessions,
            trusted_device_repo=self.devices,
            uow=self.uow,
            verify_fn=_verify_password,
        )

    def totp_login(self) -> TotpLogin:
        return TotpLogin(
            user_repo=self.users,
            settings_repo=self.settings,
            attempts=self.attempts,
            replay_guard=self.replay_guard,
            session_repo=self.sessions,
            trusted_device_repo=self.devices,
            uow=self.uow,
        )


def password_cmd(
    username: str = "alice", password: str = PASSWORD, *, cookie: str | None = None
) -> PasswordLoginCommand:
    return PasswordLoginCommand(
        username=username,
        password=password,
        client_ip=CLIENT_IP,
        user_agent=USER_AGENT,
        trusted_device_secret=cookie,
    )


def totp_cmd(partial_token: str, code: str, *, trust_device: bool = False) -> TotpLoginCommand:
    return TotpLoginCommand(
        partial_token=partial_token,
        totp_code=code,
        trust_device=trust_device,
        client_ip=CLIENT_IP,
        user_agent=USER_AGENT,
    )


def maintenance_on() -> AdminMaintenanceSettings:
    return AdminMaintenanceSettings(id=1, enabled=True, message="Down for upgrades")


# ── PasswordLogin ─────────────────────────────────────────────────────


class TestPasswordLoginSession:
    async def test_correct_credentials_issue_a_committed_session(self):
        h = Harness([make_user()])

        result = await h.password_login().execute(password_cmd())

        assert isinstance(result, SessionIssued)
        assert result.cookie_max_age == SESSION_COOKIE_MAX_AGE_SECONDS
        assert result.trusted_device is None
        [session] = h.sessions.saved
        assert (session.user_id, session.ip, session.user_agent) == (7, CLIENT_IP, USER_AGENT)
        payload = get_token_payload(result.access_token, persistent=False)
        assert payload is not None
        assert payload.sub == "7"
        assert payload.sid == str(session.public_id)
        assert h.uow.committed

    async def test_last_logged_in_is_stamped(self):
        user = make_user(last_logged_in=None)
        h = Harness([user])

        await h.password_login().execute(password_cmd())

        assert user.last_logged_in is not None
        assert h.users.saved == [user]

    async def test_a_missing_auth_settings_row_falls_back_to_local_passwords(self):
        h = Harness([make_user()], settings=FakeSettingsRepository(auth_missing=True))

        result = await h.password_login().execute(password_cmd())

        assert isinstance(result, SessionIssued)


class TestPasswordLoginFailures:
    async def test_a_wrong_password_is_counted_under_the_normalised_name(self):
        h = Harness([make_user()])

        with pytest.raises(UserNotFoundError):
            await h.password_login().execute(password_cmd("  ALICE ", "wrong"))

        assert h.attempts.failures["alice"] == 1
        assert h.attempts.failures[PAIR_KEY] == 1
        assert h.sessions.saved == []

    async def test_an_unknown_name_is_counted_like_a_wrong_password(self):
        h = Harness([make_user()])

        with pytest.raises(UserNotFoundError) as exc_info:
            await h.password_login().execute(password_cmd("nobody", "wrong"))

        assert type(exc_info.value) is UserNotFoundError
        assert h.attempts.failures["nobody"] == 1

    async def test_reaching_the_limit_locks_for_the_configured_duration(self):
        settings = FakeSettingsRepository(
            security=make_security(max_login_attempts=2, lockout_duration_minutes=3)
        )
        h = Harness([make_user()], settings=settings)

        for _ in range(2):
            with pytest.raises(UserNotFoundError):
                await h.password_login().execute(password_cmd(password="wrong"))

        # The pair locks for the configured duration; the name alone only
        # earns the first, one second step of its growing delay.
        assert h.attempts.locks == {PAIR_KEY: 180, DELAY_KEY: 1}

    async def test_unlimited_attempts_never_lock(self):
        h = Harness([make_user()])

        for _ in range(10):
            with pytest.raises(UserNotFoundError):
                await h.password_login().execute(password_cmd(password="wrong"))

        assert h.attempts.locks == {}

    async def test_a_locked_name_is_refused_before_the_password_is_checked(self):
        directory = FakeDirectory()
        user = make_user(auth_provider=AuthProvider.LDAP)
        settings = FakeSettingsRepository(auth=make_auth(ldap_enabled=True))
        h = Harness([user], settings=settings, ldap=directory)
        h.attempts.locks[PAIR_KEY] = 42

        with pytest.raises(LoginLockedError) as exc_info:
            await h.password_login().execute(password_cmd("Alice"))

        assert exc_info.value.retry_after_seconds == 42
        assert directory.binds == 0
        assert h.attempts.failures == {}
        assert h.attempts.resets == []

    async def test_a_directory_outage_answers_like_a_wrong_password_but_is_not_counted(self):
        user = make_user(auth_provider=AuthProvider.LDAP)
        settings = FakeSettingsRepository(auth=make_auth(ldap_enabled=True))
        h = Harness([user], settings=settings, ldap=FakeDirectory(unreachable=True))

        with pytest.raises(CredentialsUnverifiableError):
            await h.password_login().execute(password_cmd())

        assert h.attempts.failures == {}

    async def test_an_inactive_account_with_the_right_password_is_refused_without_a_reset(
        self,
    ):
        h = Harness([make_user(is_active=False)])
        h.attempts.failures["alice"] = 2

        with pytest.raises(InactiveUserError):
            await h.password_login().execute(password_cmd())

        assert h.attempts.failures == {"alice": 2}
        assert h.attempts.resets == []

    async def test_an_inactive_account_with_a_wrong_password_is_a_plain_failure(self):
        h = Harness([make_user(is_active=False)])

        with pytest.raises(UserNotFoundError):
            await h.password_login().execute(password_cmd(password="wrong"))

        assert h.attempts.failures["alice"] == 1


class TestPasswordLoginSettingGates:
    async def test_disabled_local_login_refuses_before_the_counter_is_reset(self):
        settings = FakeSettingsRepository(security=make_security(allow_local_login=False))
        h = Harness([make_user()], settings=settings)

        with pytest.raises(LocalLoginDisabledError):
            await h.password_login().execute(password_cmd())

        assert h.attempts.resets == []
        assert settings.maintenance_reads == 0

    async def test_disabled_local_login_still_answers_a_wrong_password_with_the_401_error(self):
        settings = FakeSettingsRepository(security=make_security(allow_local_login=False))
        h = Harness([make_user()], settings=settings)

        with pytest.raises(UserNotFoundError):
            await h.password_login().execute(password_cmd(password="wrong"))

    async def test_maintenance_refuses_after_the_counter_is_reset(self):
        settings = FakeSettingsRepository(maintenance=maintenance_on())
        h = Harness([make_user()], settings=settings)

        with pytest.raises(MaintenanceModeError):
            await h.password_login().execute(password_cmd())

        assert h.attempts.resets == SUCCESS_RESETS
        assert h.sessions.saved == []

    async def test_maintenance_still_answers_a_wrong_password_with_the_401_error(self):
        settings = FakeSettingsRepository(maintenance=maintenance_on())
        h = Harness([make_user()], settings=settings)

        with pytest.raises(UserNotFoundError):
            await h.password_login().execute(password_cmd(password="wrong"))

        assert settings.maintenance_reads == 0

    async def test_maintenance_blocks_before_a_totp_challenge_is_handed_out(self):
        settings = FakeSettingsRepository(maintenance=maintenance_on())
        h = Harness([make_user(totp_enabled=True, totp_secret="S")], settings=settings)

        with pytest.raises(MaintenanceModeError):
            await h.password_login().execute(password_cmd())

    async def test_a_settings_holder_passes_maintenance(self):
        settings = FakeSettingsRepository(maintenance=maintenance_on())
        admin = make_user(permissions=[Permission.WRITE_SETTINGS], totp_enabled=True)
        h = Harness([admin], settings=settings)

        result = await h.password_login().execute(password_cmd())

        assert isinstance(result, TotpChallengeIssued)


class TestPasswordLoginSecondFactor:
    async def test_an_enrolled_user_gets_a_challenge_and_no_session(self):
        settings = FakeSettingsRepository(security=make_security(totp_trusted_device_days=30))
        user = make_user(totp_enabled=True, totp_secret="S", last_logged_in=None)
        h = Harness([user], settings=settings)

        result = await h.password_login().execute(password_cmd())

        assert isinstance(result, TotpChallengeIssued)
        assert result.trusted_device_days == 30
        payload = get_token_payload(result.partial_token, persistent=False)
        assert payload is not None
        assert (payload.sub, payload.scope) == ("7", token_scope.TOTP_PENDING)
        assert h.sessions.saved == []
        assert user.last_logged_in is None
        assert h.attempts.resets == SUCCESS_RESETS

    async def test_the_system_user_is_offered_no_trusted_device(self):
        settings = FakeSettingsRepository(security=make_security(totp_trusted_device_days=30))
        system = make_user(username="system", is_systemuser=True, totp_enabled=True)
        h = Harness([system], settings=settings)

        result = await h.password_login().execute(password_cmd("system"))

        assert isinstance(result, TotpChallengeIssued)
        assert result.trusted_device_days == 0

    async def test_enforced_2fa_without_enrolment_asks_for_setup(self):
        settings = FakeSettingsRepository(security=make_security(enforce_totp=True))
        h = Harness([make_user(token_version=3)], settings=settings)

        result = await h.password_login().execute(password_cmd())

        assert isinstance(result, TotpSetupRequired)
        assert result.username == "alice"
        payload = get_token_payload(result.setup_token, persistent=False)
        assert payload is not None
        assert (payload.sub, payload.ver, payload.scope) == ("7", 3, token_scope.TOTP_SETUP)
        assert h.sessions.saved == []

    async def test_a_settings_holder_must_enrol_even_without_enforcement(self):
        h = Harness([make_user(permissions=[Permission.WRITE_SETTINGS])])

        result = await h.password_login().execute(password_cmd())

        assert isinstance(result, TotpSetupRequired)


class TestPasswordLoginTrustedDevice:
    def _device(self, secret: str, *, user_id: int = 7, trust_days: int = 30) -> TrustedDevice:
        return make_trusted_device(
            user_id=user_id,
            token_hash=hash_trusted_device(secret),
            trust_days=trust_days,
            user_agent=None,
        )

    def _harness(self, device: TrustedDevice, *, trust_days: int = 30) -> Harness:
        settings = FakeSettingsRepository(
            security=make_security(totp_trusted_device_days=trust_days)
        )
        user = make_user(totp_enabled=True, totp_secret="S")
        return Harness([user], settings=settings, devices=[device])

    async def test_a_live_grant_skips_the_challenge(self):
        device = self._device("cookie-secret")
        before = device.last_used_at
        h = self._harness(device)

        result = await h.password_login().execute(password_cmd(cookie="cookie-secret"))

        assert isinstance(result, SessionIssued)
        assert result.trusted_device is None
        assert h.devices.saved == [device]
        assert device.last_used_at >= before
        assert len(h.sessions.saved) == 1

    async def test_another_users_grant_is_ignored(self):
        h = self._harness(self._device("cookie-secret", user_id=99))

        result = await h.password_login().execute(password_cmd(cookie="cookie-secret"))

        assert isinstance(result, TotpChallengeIssued)
        assert h.devices.saved == []

    async def test_a_revoked_grant_is_ignored(self):
        device = self._device("cookie-secret")
        device.revoked_at = device.created_at
        h = self._harness(device)

        result = await h.password_login().execute(password_cmd(cookie="cookie-secret"))

        assert isinstance(result, TotpChallengeIssued)

    async def test_an_unknown_cookie_is_ignored(self):
        h = self._harness(self._device("cookie-secret"))

        result = await h.password_login().execute(password_cmd(cookie="other"))

        assert isinstance(result, TotpChallengeIssued)

    async def test_turning_the_feature_off_disarms_existing_grants(self):
        h = self._harness(self._device("cookie-secret"), trust_days=0)

        result = await h.password_login().execute(password_cmd(cookie="cookie-secret"))

        assert isinstance(result, TotpChallengeIssued)
        assert result.trusted_device_days == 0
        assert h.devices.lookups == 0


# ── TotpLogin ─────────────────────────────────────────────────────────


def enrolled_user(**overrides: Any) -> User:
    return make_user(totp_enabled=True, totp_secret=generate_totp_secret(), **overrides)


def code_for(user: User) -> str:
    assert user.totp_secret is not None
    return pyotp.TOTP(user.totp_secret).now()


class TestTotpLoginChallenge:
    async def test_a_garbage_token_must_start_over(self):
        h = Harness([enrolled_user()])

        with pytest.raises(TOTPChallengeInvalidError):
            await h.totp_login().execute(totp_cmd("not-a-token", "123456"))

    async def test_a_setup_token_is_not_a_challenge(self):
        user = enrolled_user()
        h = Harness([user])

        with pytest.raises(TOTPChallengeInvalidError):
            await h.totp_login().execute(totp_cmd(create_setup_token(user.id, 0), code_for(user)))

    async def test_a_deleted_user_must_start_over(self):
        h = Harness([])

        with pytest.raises(TOTPChallengeInvalidError):
            await h.totp_login().execute(totp_cmd(create_partial_token(7), "123456"))


class TestTotpLoginRefusals:
    async def test_a_locked_challenge_is_refused_before_the_account_state_is_read(self):
        user = enrolled_user(is_active=False)
        h = Harness([user])
        h.attempts.locks["totp:7"] = 120

        with pytest.raises(LoginLockedError) as exc_info:
            await h.totp_login().execute(totp_cmd(create_partial_token(7), code_for(user)))

        assert exc_info.value.retry_after_seconds == 120
        assert h.replay_guard.claimed == set()

    async def test_an_inactive_account_is_refused(self):
        user = enrolled_user(is_active=False)
        h = Harness([user])

        with pytest.raises(InactiveUserError):
            await h.totp_login().execute(totp_cmd(create_partial_token(7), code_for(user)))

    async def test_an_account_without_2fa_is_refused(self):
        h = Harness([make_user(totp_enabled=False, totp_secret=None)])

        with pytest.raises(TOTPNotEnabledError):
            await h.totp_login().execute(totp_cmd(create_partial_token(7), "123456"))

    async def test_a_wrong_code_is_counted(self):
        h = Harness([enrolled_user()])

        with pytest.raises(InvalidTOTPCodeError):
            await h.totp_login().execute(totp_cmd(create_partial_token(7), "000000x"))

        assert h.attempts.failures == {"totp:7": 1}
        assert h.sessions.saved == []

    async def test_the_last_allowed_wrong_code_locks_the_challenge(self):
        h = Harness([enrolled_user()])

        for _ in range(TOTP_MAX_ATTEMPTS):
            with pytest.raises(InvalidTOTPCodeError):
                await h.totp_login().execute(totp_cmd(create_partial_token(7), "000000x"))

        assert h.attempts.locks == {"totp:7": TOTP_LOCK_SECONDS}

    async def test_a_replayed_code_is_refused_and_counted(self):
        user = enrolled_user()
        h = Harness([user])
        code = code_for(user)
        await h.totp_login().execute(totp_cmd(create_partial_token(7), code))

        with pytest.raises(InvalidTOTPCodeError):
            await h.totp_login().execute(totp_cmd(create_partial_token(7), code))

        assert h.attempts.failures == {"totp:7": 1}
        assert all(key.startswith("glados:totp:used:login:7:") for key in h.replay_guard.claimed)

    async def test_disabled_local_login_refuses_after_the_code_verified(self):
        user = enrolled_user()
        settings = FakeSettingsRepository(security=make_security(allow_local_login=False))
        h = Harness([user], settings=settings)

        with pytest.raises(LocalLoginDisabledError):
            await h.totp_login().execute(totp_cmd(create_partial_token(7), code_for(user)))

        assert h.attempts.resets == ["totp:7"]
        assert h.sessions.saved == []

    async def test_maintenance_refuses_after_the_code_verified(self):
        user = enrolled_user()
        settings = FakeSettingsRepository(maintenance=maintenance_on())
        h = Harness([user], settings=settings)

        with pytest.raises(MaintenanceModeError):
            await h.totp_login().execute(totp_cmd(create_partial_token(7), code_for(user)))

        assert h.attempts.resets == ["totp:7"]
        assert h.sessions.saved == []

    async def test_maintenance_still_answers_a_wrong_code_with_the_code_error(self):
        settings = FakeSettingsRepository(maintenance=maintenance_on())
        h = Harness([enrolled_user()], settings=settings)

        with pytest.raises(InvalidTOTPCodeError):
            await h.totp_login().execute(totp_cmd(create_partial_token(7), "000000x"))

        assert settings.maintenance_reads == 0


class TestTotpLoginSession:
    async def test_a_valid_code_issues_a_session_without_trust(self):
        user = enrolled_user(last_logged_in=None)
        h = Harness([user])
        h.attempts.failures["totp:7"] = 3

        result = await h.totp_login().execute(totp_cmd(create_partial_token(7), code_for(user)))

        assert result.trusted_device is None
        assert result.cookie_max_age == SESSION_COOKIE_MAX_AGE_SECONDS
        assert user.last_logged_in is not None
        assert h.attempts.failures == {}
        assert len(h.sessions.saved) == 1
        assert h.devices.saved == []
        assert h.uow.committed

    async def test_trusting_the_device_grants_a_hashed_secret(self):
        user = enrolled_user()
        settings = FakeSettingsRepository(security=make_security(totp_trusted_device_days=30))
        h = Harness([user], settings=settings)

        result = await h.totp_login().execute(
            totp_cmd(create_partial_token(7), code_for(user), trust_device=True)
        )

        assert result.trusted_device is not None
        assert result.trusted_device.max_age_seconds == 30 * 86400
        [device] = h.devices.saved
        assert device.token_hash == hash_trusted_device(result.trusted_device.secret)
        assert device.token_hash != result.trusted_device.secret
        assert (device.user_id, device.user_agent) == (7, USER_AGENT)

    async def test_trust_is_not_granted_while_the_feature_is_off(self):
        user = enrolled_user()
        h = Harness([user])

        result = await h.totp_login().execute(
            totp_cmd(create_partial_token(7), code_for(user), trust_device=True)
        )

        assert result.trusted_device is None
        assert h.devices.saved == []

    async def test_the_system_user_gets_a_short_session_and_never_a_grant(self):
        system = enrolled_user(username="system", is_systemuser=True)
        settings = FakeSettingsRepository(security=make_security(totp_trusted_device_days=30))
        h = Harness([system], settings=settings)

        result = await h.totp_login().execute(
            totp_cmd(create_partial_token(7), code_for(system), trust_device=True)
        )

        assert result.cookie_max_age == SYSTEM_USER_SESSION_LIFETIME_MINUTES * 60
        assert result.trusted_device is None
        assert h.devices.saved == []
