"""
Unit coverage for PasskeyLogin's account checks after the signature
verified, the directory recheck rule, and the password-login stamps that
recheck relies on. The verifier is faked here; the real ceremony runs end
to end in tests/integration/test_api_passkeys.py.
"""

from datetime import timedelta
from typing import Any

import pyotp
import pytest

from src.modules.platform.application.dto.login_dto import SessionIssued
from src.modules.platform.application.dto.login_dto import TotpChallengeIssued
from src.modules.platform.application.dto.passkey_dto import PasskeyLoginCommand
from src.modules.platform.application.use_cases.auth.passkey_login import BeginPasskeyLogin
from src.modules.platform.application.use_cases.auth.passkey_login import PasskeyLogin
from src.modules.platform.domain.entities.passkey import Passkey
from src.modules.platform.domain.entities.passkey import make_passkey
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InactiveUserError
from src.modules.platform.domain.exceptions import MaintenanceModeError
from src.modules.platform.domain.exceptions import PasskeyPasswordRequiredError
from src.modules.platform.domain.exceptions import PasskeyRejectedError
from src.modules.platform.domain.services.login_policy import PASSKEY_DIRECTORY_RECHECK_DAYS
from src.modules.platform.domain.services.login_policy import passkey_needs_password
from src.modules.platform.domain.value_objects.auth_provider import AuthProvider
from src.modules.platform.infrastructure.security.totp import generate_totp_secret
from src.modules.platform.ports.outbound.passkey_verifier_port import PasskeyOptions
from src.shared_kernel.domain.services.clock import now_utc
from tests.unit.test_login_use_cases import FakeSettingsRepository
from tests.unit.test_login_use_cases import Harness
from tests.unit.test_login_use_cases import maintenance_on
from tests.unit.test_login_use_cases import make_auth
from tests.unit.test_login_use_cases import make_user
from tests.unit.test_login_use_cases import password_cmd
from tests.unit.test_login_use_cases import totp_cmd

CREDENTIAL_ID = b"credential-1"


class FakeVerifier:
    """Accepts every signature unless told otherwise and counts up."""

    def __init__(self, *, accept: bool = True) -> None:
        self.accept = accept
        self.verified = 0

    def authentication_options(self) -> PasskeyOptions:
        return PasskeyOptions(options={"challenge": "abc"}, challenge="abc")

    def credential_id_of(self, credential: dict[str, Any]) -> bytes | None:
        raw = credential.get("rawId")
        return raw.encode() if isinstance(raw, str) else None

    def verify_authentication(
        self, *, credential: dict[str, Any], challenge: str, public_key: bytes, sign_count: int
    ) -> int:
        if not self.accept:
            raise PasskeyRejectedError("bad signature")
        self.verified += 1
        return sign_count + 1


class FakePasskeyRepository:
    def __init__(self, passkeys: list[Passkey]) -> None:
        self.passkeys = {p.credential_id: p for p in passkeys}
        self.saved: list[Passkey] = []

    async def get_by_credential_id(self, credential_id: bytes) -> Passkey | None:
        return self.passkeys.get(credential_id)

    async def save(self, passkey: Passkey) -> Passkey:
        self.saved.append(passkey)
        return passkey


def a_passkey(user_id: int = 7) -> Passkey:
    return make_passkey(
        user_id=user_id,
        credential_id=CREDENTIAL_ID,
        public_key=b"key",
        sign_count=3,
        name="Laptop",
        transports=["internal"],
        backed_up=False,
    )


class PasskeyHarness(Harness):
    def __init__(
        self,
        users: list[User],
        *,
        settings: FakeSettingsRepository | None = None,
        verifier: FakeVerifier | None = None,
    ) -> None:
        super().__init__(users, settings=settings)
        self.verifier = verifier or FakeVerifier()
        self.passkeys = FakePasskeyRepository([a_passkey()])

    def login(self) -> PasskeyLogin:
        return PasskeyLogin(
            user_repo=self.users,
            settings_repo=self.settings,
            attempts=self.attempts,
            session_repo=self.sessions,
            passkey_repo=self.passkeys,
            replay_guard=self.replay_guard,
            verifier=self.verifier,
            uow=self.uow,
        )

    def cmd(self, *, raw_id: str = CREDENTIAL_ID.decode()) -> PasskeyLoginCommand:
        challenge = BeginPasskeyLogin(self.verifier).execute()
        return PasskeyLoginCommand(
            challenge_token=challenge.challenge_token,
            credential={"rawId": raw_id},
            client_ip="10.0.0.7",
            user_agent="pytest-browser",
        )


def ldap_on() -> FakeSettingsRepository:
    return FakeSettingsRepository(auth=make_auth(ldap_enabled=True))


class TestPasskeyLogin:
    async def test_a_verified_passkey_issues_a_session_without_totp(self):
        user = make_user(totp_enabled=True, totp_secret=generate_totp_secret())
        h = PasskeyHarness([user])

        result = await h.login().execute(h.cmd())

        assert isinstance(result, SessionIssued)
        assert h.uow.committed
        [stamped] = h.passkeys.saved
        assert stamped.sign_count == 4
        assert stamped.last_used_at is not None
        assert user.last_logged_in is not None

    async def test_a_challenge_is_redeemed_once(self):
        h = PasskeyHarness([make_user()])
        cmd = h.cmd()
        await h.login().execute(cmd)

        with pytest.raises(PasskeyRejectedError):
            await h.login().execute(cmd)

    async def test_an_unknown_credential_is_rejected_before_verifying(self):
        h = PasskeyHarness([make_user()])

        with pytest.raises(PasskeyRejectedError):
            await h.login().execute(h.cmd(raw_id="someone-else"))
        assert h.verifier.verified == 0

    async def test_account_state_is_looked_at_only_after_the_signature(self):
        h = PasskeyHarness([make_user(is_active=False)], verifier=FakeVerifier(accept=False))

        with pytest.raises(PasskeyRejectedError):
            await h.login().execute(h.cmd())

    async def test_an_inactive_account_is_refused(self):
        h = PasskeyHarness([make_user(is_active=False)])

        with pytest.raises(InactiveUserError):
            await h.login().execute(h.cmd())
        assert h.sessions.saved == []

    async def test_maintenance_mode_applies(self):
        settings = FakeSettingsRepository(maintenance=maintenance_on())
        h = PasskeyHarness([make_user()], settings=settings)

        with pytest.raises(MaintenanceModeError):
            await h.login().execute(h.cmd())

    async def test_a_directory_account_with_a_stale_password_check_is_refused(self):
        stale = now_utc() - timedelta(days=PASSKEY_DIRECTORY_RECHECK_DAYS + 1)
        user = make_user(auth_provider=AuthProvider.LDAP, password_verified_at=stale)
        h = PasskeyHarness(
            [user], settings=FakeSettingsRepository(auth=make_auth(ldap_enabled=True))
        )

        with pytest.raises(PasskeyPasswordRequiredError):
            await h.login().execute(h.cmd())
        assert h.sessions.saved == []

    async def test_a_directory_account_with_a_recent_password_check_signs_in(self):
        user = make_user(auth_provider=AuthProvider.LDAP, password_verified_at=now_utc())
        h = PasskeyHarness(
            [user], settings=FakeSettingsRepository(auth=make_auth(ldap_enabled=True))
        )

        assert isinstance(await h.login().execute(h.cmd()), SessionIssued)


class TestPasskeyNeedsPassword:
    def test_local_accounts_never_need_it(self):
        assert not passkey_needs_password(make_user(), ldap_enabled=True, now=now_utc())

    def test_directory_accounts_need_a_first_check(self):
        user = make_user(auth_provider=AuthProvider.LDAP)
        assert passkey_needs_password(user, ldap_enabled=True, now=now_utc())

    def test_directory_accounts_are_local_while_ldap_is_off(self):
        user = make_user(auth_provider=AuthProvider.LDAP)
        assert not passkey_needs_password(user, ldap_enabled=False, now=now_utc())

    def test_the_window_is_inclusive_of_its_last_day(self):
        now = now_utc()
        user = make_user(
            auth_provider=AuthProvider.LDAP,
            password_verified_at=now - timedelta(days=PASSKEY_DIRECTORY_RECHECK_DAYS),
        )
        assert not passkey_needs_password(user, ldap_enabled=True, now=now)


class TestPasswordLoginStampsTheCheck:
    async def test_a_password_login_stamps_it(self):
        user = make_user()
        h = Harness([user])

        await h.password_login().execute(password_cmd())

        assert user.password_verified_at is not None

    async def test_the_totp_step_stamps_it(self):
        secret = generate_totp_secret()
        user = make_user(totp_enabled=True, totp_secret=secret)
        h = Harness([user])
        challenge = await h.password_login().execute(password_cmd())
        assert isinstance(challenge, TotpChallengeIssued)
        user.password_verified_at = None

        await h.totp_login().execute(totp_cmd(challenge.partial_token, pyotp.TOTP(secret).now()))

        assert user.password_verified_at is not None
