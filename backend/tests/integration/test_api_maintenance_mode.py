"""
Backend enforcement of the Maintenance tab settings (enabled / message /
allowed_ips). The entity docstring has promised "when enabled all
non-admin API requests return 503" for a while; nothing consumed it until
now (see maintenance_policy.py). This is the HTTP-level proof of the
"API contract" section of the maintenance-mode plan:

  - every gated surface (web session, PAT, API key, both login endpoints)
    returns 503 with `code: "MaintenanceModeError"` for a non-exempt
    caller, and the admin message (or the fixed fallback) as `detail`;
  - three independent exemptions: the system user, write:settings, and an
    allowlisted client IP or CIDR network;
  - /public/branding and /host/capabilities expose enabled/message so the
    frontend can show a notice instead of waiting for a 503;
  - PUT validates allowed_ips (IP/CIDR only, trimmed and deduplicated) and
    message (max 500 chars).

`_seed_admin_settings` (conftest.py, autouse) also seeds
admin_maintenance_settings disabled; without that every authenticated
request in the whole suite would 500, because auth_deps.py reads it. See
that fixture's own comment.
"""

import httpx
import pyotp
import pytest

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.platform.adapters.outbound.persistence.repositories.api_key_repository import (
    SqlAlchemyApiKeyRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.api_key_dto import CreateApiKeyCommand
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.api_key.create_api_key import CreateApiKey
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.domain.entities.admin_settings.branding import AdminBrandingSettings
from src.modules.platform.domain.entities.admin_settings.features import AdminFeatureSettings
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.entities.admin_settings.maintenance import AdminMaintenanceSettings
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.security.hashing import aget_hash
from src.modules.platform.infrastructure.security.token import create_partial_token
from src.modules.platform.infrastructure.security.totp import generate_totp_secret
from tests.integration.conftest import _TEST_BASE_URL
from tests.integration.conftest import auth_headers

PASSWORD = "test-password"
VALUES_URL = "/api/v1/web/host/values"
MAINTENANCE_URL = "/api/v1/web/admin/settings/maintenance"


def _client_from(address: tuple[str, int]) -> httpx.AsyncClient:
    """A client whose requests arrive from `address`, for the IP allowlist."""
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=address),
        base_url=_TEST_BASE_URL,
        follow_redirects=True,
    )


async def _set_maintenance(
    db, *, enabled: bool, message: str | None = None, allowed_ips: list[str] | None = None
) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_maintenance(
        AdminMaintenanceSettings(
            id=1, enabled=enabled, message=message, allowed_ips=allowed_ips or []
        )
    )
    await db.commit()


async def _seed_security(
    db, *, allow_local_login: bool = True, enable_api_key_auth: bool = False
) -> None:
    """login_access_token/login_totp and get_current_api_key_user all read
    AdminSecuritySettings; this integration DB never runs InitDatabase (see
    conftest.py's module docstring), so any test that reaches those lines
    needs the row seeded first, same pattern as test_api_totp_lockout.py's
    own _seed_security."""
    await SqlAlchemyAdminSettingsRepository(db).save_security(
        AdminSecuritySettings(
            id=1,
            enforce_totp=False,
            allow_rfid_login=True,
            allow_local_login=allow_local_login,
            enable_api_key_auth=enable_api_key_auth,
            min_password_length=8,
            session_timeout_minutes=1440,
            totp_trusted_device_days=30,
            max_login_attempts=0,
            lockout_duration_minutes=15,
            token_max_lifetime_days=3650,
        )
    )
    await db.commit()


async def _seed_branding(db) -> None:
    """/public/branding also reads the branding domain, unseeded by
    _seed_admin_settings, same reasoning as test_api_public_branding.py."""
    await SqlAlchemyAdminSettingsRepository(db).save_branding(
        AdminBrandingSettings(
            id=1,
            app_name="Glados",
            app_description=None,
            footer_text=None,
            logo_url=None,
            favicon_url=None,
            logo_key=None,
            favicon_key=None,
            login_background_video_key=None,
        )
    )
    await db.commit()


async def _login(client, username="tester", password=PASSWORD):
    return await client.post(
        "/api/v1/auth/login/access-token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


class TestGatedEndpointReturns503:
    async def test_plain_user_is_blocked(self, client, create_user, db):
        user = await create_user()
        await _set_maintenance(db, enabled=True, message="Down for upgrades.")

        response = await client.get(VALUES_URL, headers=await auth_headers(user))

        assert response.status_code == 503
        body = response.json()
        assert body["code"] == "MaintenanceModeError"
        assert body["detail"] == "Down for upgrades."

    async def test_null_message_falls_back_to_the_default(self, client, create_user, db):
        user = await create_user()
        await _set_maintenance(db, enabled=True, message=None)

        response = await client.get(VALUES_URL, headers=await auth_headers(user))

        assert response.status_code == 503
        assert (
            response.json()["detail"] == "The system is under maintenance. Please try again later."
        )

    async def test_disabled_lets_a_plain_user_through(self, client, create_user, db):
        user = await create_user()
        await _set_maintenance(db, enabled=False)

        response = await client.get(VALUES_URL, headers=await auth_headers(user))

        assert response.status_code == 200


class TestExemptions:
    async def test_write_settings_holder_passes(self, client, create_user, db):
        user = await create_user(permissions=[Permission.WRITE_SETTINGS])
        await _set_maintenance(db, enabled=True)

        response = await client.get(VALUES_URL, headers=await auth_headers(user))

        assert response.status_code == 200

    async def test_system_user_passes(self, client, create_user, db):
        user = await create_user(username="system", email="system@example.com", is_systemuser=True)
        await _set_maintenance(db, enabled=True)

        response = await client.get(VALUES_URL, headers=await auth_headers(user))

        assert response.status_code == 200

    async def test_the_exemption_does_not_leak_to_ordinary_users(self, client, create_user, db):
        system = await create_user(
            username="system", email="system@example.com", is_systemuser=True
        )
        plain = await create_user()
        await _set_maintenance(db, enabled=True)

        assert (await client.get(VALUES_URL, headers=await auth_headers(system))).status_code == 200
        assert (await client.get(VALUES_URL, headers=await auth_headers(plain))).status_code == 503

    async def test_allowlisted_ip_passes(self, create_user, db):
        user = await create_user()
        await _set_maintenance(db, enabled=True, allowed_ips=["10.1.2.3"])
        allowed_client = _client_from(("10.1.2.3", 1234))
        allowed_client.headers.update(await auth_headers(user))

        assert (await allowed_client.get(VALUES_URL)).status_code == 200

    async def test_cidr_allowlist_member_passes(self, create_user, db):
        user = await create_user()
        await _set_maintenance(db, enabled=True, allowed_ips=["10.1.0.0/16"])
        member_client = _client_from(("10.1.2.3", 1234))
        member_client.headers.update(await auth_headers(user))

        assert (await member_client.get(VALUES_URL)).status_code == 200

    async def test_cidr_allowlist_non_member_is_blocked(self, create_user, db):
        user = await create_user()
        await _set_maintenance(db, enabled=True, allowed_ips=["10.1.0.0/16"])
        other_client = _client_from(("10.2.0.1", 1))
        other_client.headers.update(await auth_headers(user))

        assert (await other_client.get(VALUES_URL)).status_code == 503


class TestWriteSettingsCanReachTheSwitchWhileBlocked:
    """The point of the write:settings exemption: whoever can turn
    maintenance mode off must be able to reach the switch while it's on."""

    async def test_put_maintenance_still_succeeds_when_already_enabled(self, auth_client, db):
        writer = await auth_client(
            permissions=[Permission.WRITE_SETTINGS, Permission.READ_SETTINGS]
        )
        await _set_maintenance(db, enabled=True, message="Down for upgrades.")

        response = await writer.put(
            MAINTENANCE_URL,
            json={"enabled": True, "message": "Down for upgrades.", "allowed_ips": []},
        )

        assert response.status_code == 200, response.text


class TestLoginGate:
    async def test_plain_user_password_login_is_blocked(self, client, create_user, db):
        await create_user()
        await _seed_security(db)
        await _set_maintenance(db, enabled=True, message="Down for upgrades.")

        response = await _login(client)

        assert response.status_code == 503
        assert response.json()["code"] == "MaintenanceModeError"

    async def test_system_user_can_still_log_in(self, client, create_user, db):
        await create_user(username="system", email="system@example.com", is_systemuser=True)
        await _seed_security(db)
        await _set_maintenance(db, enabled=True)

        assert (await _login(client, username="system")).status_code == 200

    async def test_wrong_credentials_still_401_when_blocked(self, client, create_user, db):
        """Checked after the password, so a bad password cannot be used to
        discover that maintenance mode is on."""
        await create_user()
        await _seed_security(db)
        await _set_maintenance(db, enabled=True)

        assert (await _login(client, password="wrong")).status_code == 401

    async def test_disabled_lets_a_plain_user_log_in(self, client, create_user, db):
        await create_user()
        await _seed_security(db)
        await _set_maintenance(db, enabled=False)

        assert (await _login(client)).status_code == 200


class TestTotpStepGate:
    """A blocked user must not be handed a challenge token they can never
    redeem (web_login.py's own check), and even a *verified* code must not
    complete the login while blocked."""

    async def _enrol(self, create_user, db, **kw):
        user = await create_user(password=PASSWORD, **kw)
        secret = generate_totp_secret()
        user.totp_secret = secret
        user.totp_enabled = True
        saved = await SqlAlchemyUserRepository(db).save(user)
        await db.commit()
        return saved, secret

    async def test_a_verified_code_is_still_blocked_during_maintenance(
        self, client, create_user, db
    ):
        await _seed_security(db)
        user, secret = await self._enrol(create_user, db)
        await _set_maintenance(db, enabled=True, message="Down for upgrades.")

        response = await client.post(
            "/api/v1/auth/login/totp",
            json={
                "partial_token": create_partial_token(user.id),
                "totp_code": pyotp.TOTP(secret).now(),
            },
        )

        assert response.status_code == 503
        assert response.json()["code"] == "MaintenanceModeError"

    async def test_wrong_code_still_401_when_blocked(self, client, create_user, db):
        """The setting is rechecked only after the code verifies, so a
        wrong code cannot be used to discover whether maintenance mode is
        on without already holding a valid second factor."""
        await _seed_security(db)
        user, secret = await self._enrol(create_user, db)
        await _set_maintenance(db, enabled=True)
        real = pyotp.TOTP(secret).now()
        wrong = "000000" if real != "000000" else "111111"

        response = await client.post(
            "/api/v1/auth/login/totp",
            json={"partial_token": create_partial_token(user.id), "totp_code": wrong},
        )

        assert response.status_code == 401

    async def test_system_user_totp_step_still_succeeds(self, client, create_user, db):
        await _seed_security(db)
        user, secret = await self._enrol(
            create_user, db, username="system", email="system@example.com", is_systemuser=True
        )
        await _set_maintenance(db, enabled=True)

        response = await client.post(
            "/api/v1/auth/login/totp",
            json={
                "partial_token": create_partial_token(user.id),
                "totp_code": pyotp.TOTP(secret).now(),
            },
        )

        assert response.status_code == 200


class TestPatSurfaceGate:
    async def test_a_valid_pat_is_blocked_during_maintenance(self, client, create_user, db):
        owner = await create_user(permissions=[Permission.WRITE_PAT])
        token = (
            await CreatePat(
                SqlAlchemyPatRepository(db),
                settings_repo=SqlAlchemyAdminSettingsRepository(db),
                uow=SqlAlchemyUnitOfWork(db),
            ).execute(
                actor=owner,
                cmd=CreatePatCommand(name="test-pat", permissions=[], expires_in_days=30),
            )
        ).token
        await _set_maintenance(db, enabled=True)

        response = await client.get("/api/v1/pat/users/me", headers={"X-Api-Key": token})

        assert response.status_code == 503
        assert response.json()["code"] == "MaintenanceModeError"

    async def test_disabled_lets_the_same_pat_through(self, client, create_user, db):
        owner = await create_user(permissions=[Permission.WRITE_PAT])
        token = (
            await CreatePat(
                SqlAlchemyPatRepository(db),
                settings_repo=SqlAlchemyAdminSettingsRepository(db),
                uow=SqlAlchemyUnitOfWork(db),
            ).execute(
                actor=owner,
                cmd=CreatePatCommand(name="test-pat", permissions=[], expires_in_days=30),
            )
        ).token
        await _set_maintenance(db, enabled=False)

        response = await client.get("/api/v1/pat/users/me", headers={"X-Api-Key": token})

        assert response.status_code == 200


class TestApiKeySurfaceGate:
    async def test_a_valid_key_is_blocked_during_maintenance(self, client, create_user, db):
        await _seed_security(db, enable_api_key_auth=True)
        owner = await create_user(
            username="key-owner",
            email="key-owner@example.com",
            permissions=[Permission.MANAGE_API_KEYS],
        )
        key = (
            await CreateApiKey(
                SqlAlchemyApiKeyRepository(db),
                SqlAlchemyUserRepository(db),
                SqlAlchemyUnitOfWork(db),
                settings_repo=SqlAlchemyAdminSettingsRepository(db),
                hash_password_fn=aget_hash,
            ).execute(
                actor=owner,
                cmd=CreateApiKeyCommand(name="test-key", permissions=[], expires_in_days=30),
            )
        ).key
        await _set_maintenance(db, enabled=True)

        response = await client.post(
            "/api/v1/key/users/rfid", json={"rfid": "00000000"}, headers={"X-Api-Key": key}
        )

        assert response.status_code == 503
        assert response.json()["code"] == "MaintenanceModeError"


class TestPublicBranding:
    async def test_exposes_enabled_and_message(self, client, db):
        await _seed_branding(db)
        await _set_maintenance(db, enabled=True, message="Down for upgrades.")

        response = await client.get("/api/v1/public/branding")

        assert response.status_code == 200
        assert response.json()["maintenance_enabled"] is True
        assert response.json()["maintenance_message"] == "Down for upgrades."

    async def test_exposes_disabled_and_null_message(self, client, db):
        await _seed_branding(db)
        await _set_maintenance(db, enabled=False)

        response = await client.get("/api/v1/public/branding")

        assert response.status_code == 200
        assert response.json()["maintenance_enabled"] is False
        assert response.json()["maintenance_message"] is None


async def _seed_mail_and_features(db) -> None:
    """/host/capabilities also reads mail.enabled and the feature flags,
    unseeded by conftest's autouse `_seed_admin_settings`, same reasoning
    as test_api_host_capabilities.py's own `_seed_mail_and_features`."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_mail(
        AdminMailSettings(
            id=1,
            enabled=False,
            host="",
            port=587,
            user="",
            password=None,
            from_address=None,
            use_tls=True,
            use_ssl=False,
            verify_certificate=True,
            from_display_name="",
            reply_to=None,
            send_limit_per_hour=20,
            send_lock_minutes=60,
            alert_recipients=[],
        )
    )
    await db.commit()
    await repo.save_features(
        AdminFeatureSettings(
            id=1,
            enable_email_notifications=True,
            enable_production_planning=True,
            allow_private_webhooks=False,
        )
    )
    await db.commit()


class TestHostCapabilities:
    async def test_exposes_fields_for_an_exempt_user(self, client, create_user, db):
        await _seed_mail_and_features(db)
        await _seed_security(db)
        user = await create_user(permissions=[Permission.WRITE_SETTINGS])
        await _set_maintenance(db, enabled=True, message="Down for upgrades.")

        response = await client.get(
            "/api/v1/web/host/capabilities", headers=await auth_headers(user)
        )

        assert response.status_code == 200, response.text
        assert response.json()["maintenance_enabled"] is True
        assert response.json()["maintenance_message"] == "Down for upgrades."


class TestPutValidation:
    @pytest.fixture
    async def writer(self, auth_client):
        return await auth_client(permissions=[Permission.WRITE_SETTINGS, Permission.READ_SETTINGS])

    async def test_an_invalid_entry_is_rejected_with_422(self, writer):
        response = await writer.put(
            MAINTENANCE_URL, json={"enabled": False, "allowed_ips": ["not-an-ip"]}
        )

        assert response.status_code == 422, response.text

    async def test_whitespace_and_a_duplicate_are_normalised(self, writer):
        response = await writer.put(
            MAINTENANCE_URL, json={"enabled": False, "allowed_ips": [" 10.0.0.1 ", "10.0.0.1"]}
        )

        assert response.status_code == 200, response.text
        assert response.json()["allowed_ips"] == ["10.0.0.1"]

    async def test_a_cidr_network_is_accepted(self, writer):
        response = await writer.put(
            MAINTENANCE_URL, json={"enabled": False, "allowed_ips": ["10.0.0.0/8"]}
        )

        assert response.status_code == 200, response.text
        assert response.json()["allowed_ips"] == ["10.0.0.0/8"]

    async def test_a_message_over_500_chars_is_rejected(self, writer):
        response = await writer.put(MAINTENANCE_URL, json={"enabled": False, "message": "x" * 501})

        assert response.status_code == 422, response.text

    async def test_a_message_at_exactly_500_chars_is_accepted(self, writer):
        response = await writer.put(MAINTENANCE_URL, json={"enabled": False, "message": "x" * 500})

        assert response.status_code == 200, response.text

    async def test_disabled_and_a_plain_get_still_succeeds(self, writer):
        """Sanity check the fixture/baseline: with maintenance off, a
        write:settings holder (or anyone) reads normally."""
        response = await writer.get(MAINTENANCE_URL)

        assert response.status_code == 200, response.text
        assert response.json()["enabled"] is False
