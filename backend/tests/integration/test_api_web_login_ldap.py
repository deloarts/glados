"""
Directory-backed login, driven through the real HTTP stack.

The asymmetry between the two directory failure modes is the security core:
a REJECTED credential must not fall back to the local password, while an
UNREACHABLE directory must. Both are pinned here end-to-end, not just at the
use-case level, because the wiring between endpoint and use case is exactly
where a fallback could be reintroduced by accident.

The directory itself is faked, see FakeLdapAuthenticator. The real ldap3
adapter is covered in tests/unit/test_ldap_authenticator.py, and keeping it
out of here is what lets the integration suite run with no directory server.
"""

import pytest
from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.platform.adapters.inbound.api.deps.services import get_login_attempt_tracker
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_ldap_authenticator
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.domain.entities.admin_settings.auth import AdminAuthSettings
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.exceptions import LdapUnavailableError
from src.modules.platform.domain.value_objects.auth_provider import AuthProvider
from src.modules.platform.infrastructure.security.hashing import unusable_password_hash
from src.modules.platform.infrastructure.security.hashing import verify_hash
from tests.integration.fakes import FakeLoginAttemptTracker

LOCAL_PASSWORD = "test-password"
AD_PASSWORD = "directory-password"
LOGIN_URL = "/api/v1/auth/login/access-token"


class FakeLdapAuthenticator:
    def __init__(self, verdict: bool | Exception = True) -> None:
        self.verdict = verdict
        self.calls: list[tuple[str, str]] = []

    async def authenticate(self, username: str, password: str) -> bool:
        self.calls.append((username, password))
        if isinstance(self.verdict, Exception):
            raise self.verdict
        return self.verdict


async def login(client, username="alice", password=AD_PASSWORD):
    return await client.post(
        LOGIN_URL,
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


async def _seed_auth(db, *, ldap_enabled: bool = True) -> None:
    await db.execute(text("DELETE FROM admin_auth_settings"))
    await db.commit()
    await SqlAlchemyAdminSettingsRepository(db).save_auth(
        AdminAuthSettings(
            id=1,
            ldap_enabled=ldap_enabled,
            ldap_host="dc-01.example.com",
            ldap_port=636,
            ldap_use_ssl=True,
            ldap_start_tls=False,
            ldap_verify_certificate=False,
            ldap_domain="EXAMPLE",
            ldap_timeout_seconds=5,
        )
    )
    await db.commit()


async def _seed_security(db, *, max_attempts: int = 0) -> None:
    await db.execute(text("DELETE FROM admin_security_settings"))
    await db.commit()
    await SqlAlchemyAdminSettingsRepository(db).save_security(
        AdminSecuritySettings(
            id=1,
            enforce_totp=False,
            allow_rfid_login=True,
            allow_local_login=True,
            enable_api_key_auth=False,
            min_password_length=8,
            session_timeout_minutes=0,
            totp_trusted_device_days=0,
            max_login_attempts=max_attempts,
            lockout_duration_minutes=15,
            token_max_lifetime_days=3650,
        )
    )
    await db.commit()


@pytest.fixture
def directory():
    """Override the directory for the duration of a test. Assign
    `.verdict` to script accept / reject / unreachable."""
    fake = FakeLdapAuthenticator()
    app.dependency_overrides[get_optional_ldap_authenticator] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_optional_ldap_authenticator, None)


@pytest.fixture
def tracker():
    fake = FakeLoginAttemptTracker()
    app.dependency_overrides[get_login_attempt_tracker] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_login_attempt_tracker, None)


@pytest.fixture
async def ldap_user(db, create_user):
    await _seed_auth(db)
    await _seed_security(db)
    return await create_user(
        username="alice",
        email="alice@corp.example",
        password=LOCAL_PASSWORD,
        auth_provider=AuthProvider.LDAP,
    )


# ── The directory is the only authority ───────────────────────────────


class TestDirectoryIsTheOnlyAuthority:
    async def test_directory_accepts_and_the_login_succeeds(self, client, ldap_user, directory):
        directory.verdict = True

        assert (await login(client)).status_code == 200
        assert directory.calls == [("alice", AD_PASSWORD)]

    async def test_directory_rejects_and_the_correct_local_password_does_not_help(
        self, client, ldap_user, directory
    ):
        """The security core. A disabled or password-rotated AD account must
        not survive on whatever hash we happen to have stored."""
        directory.verdict = False

        assert (await login(client, password=LOCAL_PASSWORD)).status_code == 401

    async def test_directory_unreachable_rejects_rather_than_falling_back(
        self, client, ldap_user, directory
    ):
        """The accepted cost of keeping no copy of the directory password.
        Note ldap_user still carries a real local hash, as a pre-existing row
        would after the drop-cache migration, and even that does not help."""
        directory.verdict = LdapUnavailableError("dc unreachable")

        assert (await login(client, password=LOCAL_PASSWORD)).status_code == 401

    async def test_directory_unreachable_with_a_wrong_password_still_fails(
        self, client, ldap_user, directory
    ):
        directory.verdict = LdapUnavailableError("dc unreachable")

        assert (await login(client, password="wrong")).status_code == 401

    async def test_the_error_body_never_mentions_the_directory(self, client, ldap_user, directory):
        """A 503 or an LDAP-shaped message here would tell an unauthenticated
        caller whether the DC is reachable, and whether the account exists."""
        directory.verdict = LdapUnavailableError("dc-01.example.com refused the connection")

        response = await login(client, password="wrong")
        body = response.text.lower()

        assert response.status_code == 401
        assert "ldap" not in body
        assert "directory" not in body
        assert "dc-01" not in body


# ── Nothing is cached ─────────────────────────────────────────────────


class TestNoPasswordCaching:
    async def test_a_successful_bind_writes_no_hash_back(self, client, ldap_user, directory, db):
        """No copy of the directory password may reach our database."""
        directory.verdict = True
        original_hash = ldap_user.hashed_password

        assert (await login(client)).status_code == 200

        db.expire_all()
        stored = await SqlAlchemyUserRepository(db).get_by_id(ldap_user.id)
        assert stored.hashed_password == original_hash
        assert not verify_hash(AD_PASSWORD, stored.hashed_password)

    async def test_a_later_outage_still_locks_the_user_out(self, client, ldap_user, directory):
        """Follows from the above: there is nothing to fall back to, however
        many times the user has bound successfully before."""
        directory.verdict = True
        assert (await login(client)).status_code == 200

        directory.verdict = LdapUnavailableError("dc unreachable")
        assert (await login(client)).status_code == 401


# ── The unusable sentinel ─────────────────────────────────────────────


class TestSentinelHash:
    async def test_a_provisioned_directory_user_cannot_sign_in_locally(
        self, client, ldap_user, directory, db
    ):
        """How an account created through the UI actually looks. With LDAP
        switched off globally it routes to the local path, where bcrypt would
        raise on the sentinel; that must be a 401, never a 500."""
        repo = SqlAlchemyUserRepository(db)
        stored = await repo.get_by_id(ldap_user.id)
        stored.hashed_password = unusable_password_hash()
        await repo.save(stored)
        await db.commit()
        await _seed_auth(db, ldap_enabled=False)

        assert (await login(client, password=LOCAL_PASSWORD)).status_code == 401
        assert (await login(client, password=AD_PASSWORD)).status_code == 401
        assert directory.calls == []


# ── Routing ───────────────────────────────────────────────────────────


class TestRouting:
    async def test_a_local_user_never_reaches_the_directory(
        self, client, db, create_user, directory
    ):
        await _seed_auth(db)
        await _seed_security(db)
        await create_user(username="bob", email="bob@corp.example", password=LOCAL_PASSWORD)
        directory.verdict = False

        assert (await login(client, username="bob", password=LOCAL_PASSWORD)).status_code == 200
        assert directory.calls == []

    async def test_the_system_user_signs_in_locally_while_ldap_is_on(
        self, client, db, create_user, directory
    ):
        """The break-glass path: whoever turns LDAP on against a broken DC
        must still be able to turn it off again."""
        await _seed_auth(db)
        await _seed_security(db)
        await create_user(
            username="system",
            email="system@corp.example",
            password=LOCAL_PASSWORD,
            is_systemuser=True,
            auth_provider=AuthProvider.LDAP,
        )
        directory.verdict = False

        assert (await login(client, username="system", password=LOCAL_PASSWORD)).status_code == 200
        assert directory.calls == []

    async def test_an_email_identifier_still_binds_with_the_username(
        self, client, ldap_user, directory
    ):
        directory.verdict = True

        assert (await login(client, username="alice@corp.example")).status_code == 200
        assert directory.calls == [("alice", AD_PASSWORD)]

    async def test_ldap_switched_off_globally_uses_the_local_password(
        self, client, db, create_user, directory
    ):
        await _seed_auth(db, ldap_enabled=False)
        await _seed_security(db)
        await create_user(
            username="alice",
            email="alice@corp.example",
            password=LOCAL_PASSWORD,
            auth_provider=AuthProvider.LDAP,
        )
        directory.verdict = False

        assert (await login(client, password=LOCAL_PASSWORD)).status_code == 200


# ── Lockout protects the directory's badPwdCount ──────────────────────


class TestLockoutProtectsTheDirectory:
    async def test_the_lock_trips_before_the_next_guess_reaches_the_directory(
        self, client, db, create_user, directory, tracker
    ):
        """Every failed bind burns AD's badPwdCount, so brute-forcing our
        login page could lock real accounts out company-wide. Our own lock
        has to trip first, and the proof is that the directory stops being
        called, not merely that we return 429."""
        await _seed_auth(db)
        await _seed_security(db, max_attempts=2)
        await create_user(
            username="alice",
            email="alice@corp.example",
            password=LOCAL_PASSWORD,
            auth_provider=AuthProvider.LDAP,
        )
        directory.verdict = False

        assert (await login(client, password="guess-1")).status_code == 401
        assert (await login(client, password="guess-2")).status_code == 401
        assert len(directory.calls) == 2

        assert (await login(client, password="guess-3")).status_code == 429
        assert len(directory.calls) == 2, "the third guess must never reach the directory"

    async def test_case_cycling_cannot_evade_the_lock(
        self, client, db, create_user, directory, tracker
    ):
        """AD treats alice/ALICE/Alice as one principal sharing one
        badPwdCount. If our counter keyed on the raw input, an attacker could
        cycle case to stay under our limit while still burning the
        directory's."""
        await _seed_auth(db)
        await _seed_security(db, max_attempts=2)
        await create_user(
            username="alice",
            email="alice@corp.example",
            password=LOCAL_PASSWORD,
            auth_provider=AuthProvider.LDAP,
        )
        directory.verdict = False

        assert (await login(client, username="alice", password="g1")).status_code == 401
        assert (await login(client, username="ALICE", password="g2")).status_code == 401

        assert (await login(client, username="Alice", password="g3")).status_code == 429
        assert len(directory.calls) == 2


# ── An outage must not count toward the lock ───────────────────────────


class TestOutageDoesNotCountTowardLockout:
    async def test_a_directory_outage_does_not_count_toward_the_lock(
        self, client, db, create_user, directory, tracker
    ):
        """The scenario the user asked for: a directory blip must not lock
        anyone out on credentials that were never actually judged."""
        await _seed_auth(db)
        await _seed_security(db, max_attempts=5)
        await create_user(
            username="alice",
            email="alice@corp.example",
            password=LOCAL_PASSWORD,
            auth_provider=AuthProvider.LDAP,
        )
        directory.verdict = LdapUnavailableError("dc unreachable")

        for _ in range(6):
            assert (await login(client, password="whatever")).status_code == 401

        assert tracker.failures.get("alice", 0) == 0

    async def test_a_wrong_password_still_counts_while_the_directory_is_up(
        self, client, db, create_user, directory, tracker
    ):
        """Pins that the outage fix does not disarm lockout for directory users
        generally, only outages are exempt. The 5th wrong password reaches
        the limit and locks (still answered 401, same as every failure);
        the 6th is the one that observes the lock as a 429."""
        await _seed_auth(db)
        await _seed_security(db, max_attempts=5)
        await create_user(
            username="alice",
            email="alice@corp.example",
            password=LOCAL_PASSWORD,
            auth_provider=AuthProvider.LDAP,
        )
        directory.verdict = False

        for _ in range(5):
            assert (await login(client, password="wrong")).status_code == 401

        assert (await login(client, password="wrong")).status_code == 429

    async def test_an_outage_neither_adds_to_nor_clears_an_existing_run(
        self, client, db, create_user, directory, tracker
    ):
        """3 real failures, then an outage, then 2 more real failures: the
        5th *real* failure reaches the limit and locks, the outage in the
        middle counted for neither side of the ledger."""
        await _seed_auth(db)
        await _seed_security(db, max_attempts=5)
        await create_user(
            username="alice",
            email="alice@corp.example",
            password=LOCAL_PASSWORD,
            auth_provider=AuthProvider.LDAP,
        )

        directory.verdict = False
        for _ in range(3):
            assert (await login(client, password="wrong")).status_code == 401
        assert tracker.failures.get("alice") == 3

        directory.verdict = LdapUnavailableError("dc unreachable")
        assert (await login(client, password="wrong")).status_code == 401
        assert tracker.failures.get("alice") == 3, "the outage must not add to the run"

        directory.verdict = False
        assert (await login(client, password="wrong")).status_code == 401  # 4th real failure
        assert (await login(client, password="wrong")).status_code == 401  # 5th real failure, locks

        assert (await login(client, password="wrong")).status_code == 429
