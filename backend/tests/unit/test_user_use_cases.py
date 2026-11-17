"""
Unit tests for all user use cases.
No database, no HTTP, no mail server needed.
All dependencies are replaced with in-memory fakes.
"""

import pytest

from src.modules.platform.application.dto.user_dto import CreateUserCommand
from src.modules.platform.application.dto.user_dto import UpdateUserCommand
from src.modules.platform.application.use_cases.user.authenticate_user import AuthenticateUser
from src.modules.platform.application.use_cases.user.create_user import CreateUser
from src.modules.platform.application.use_cases.user.get_user import GetUser
from src.modules.platform.application.use_cases.user.get_user import GetUsers
from src.modules.platform.application.use_cases.user.update_user import UpdateUser
from src.modules.platform.domain.entities.admin_settings.general import AdminGeneralSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import CredentialsUnverifiableError
from src.modules.platform.domain.exceptions import CurrentPasswordRequiredError
from src.modules.platform.domain.exceptions import EmailAlreadyExistsError
from src.modules.platform.domain.exceptions import InactiveUserError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import InvalidSharedAccountMemberError
from src.modules.platform.domain.exceptions import LdapUnavailableError
from src.modules.platform.domain.exceptions import PasswordConfirmationFailedError
from src.modules.platform.domain.exceptions import PasswordCriteriaError
from src.modules.platform.domain.exceptions import PasswordNotAllowedError
from src.modules.platform.domain.exceptions import ReservedUsernameError
from src.modules.platform.domain.exceptions import SystemUserProtectedError
from src.modules.platform.domain.exceptions import UsernameAlreadyExistsError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.user_rules import UserRules
from src.modules.platform.domain.value_objects.auth_provider import AuthProvider
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.security.hashing import aget_hash
from src.modules.platform.infrastructure.security.hashing import averify_hash
from src.modules.platform.infrastructure.security.hashing import is_unusable_hash
from src.modules.platform.infrastructure.security.hashing import unusable_password_hash
from src.modules.platform.infrastructure.security.hashing import verify_hash
from src.modules.platform.ports.outbound.repositories.user_repository import UserFilterDto
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork

# ── Helpers ───────────────────────────────────────────────────────────


class FakeUserRepository:
    """In-memory repository, no DB required."""

    def __init__(self, users: list[User] | None = None):
        self._users: dict[int, User] = {}
        self._next_id = 1
        for u in users or []:
            self._users[u.id] = u
            self._next_id = max(self._next_id, u.id + 1)

    async def get_by_id(self, id: int) -> User | None:
        return self._users.get(id)

    async def get_by_username(self, username: str) -> User | None:
        return next((u for u in self._users.values() if u.username == username), None)

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._users.values() if u.email == email), None)

    async def get_by_username_or_email(self, identifier: str) -> User | None:
        needle = identifier.strip().lower()
        return next(
            (
                u
                for u in sorted(self._users.values(), key=lambda u: u.id)
                if u.username.lower() == needle or (u.email or "").lower() == needle
            ),
            None,
        )

    async def get_by_rfid(self, rfid: str) -> User | None:
        from src.modules.platform.infrastructure.security.rfid import rfid_lookup

        lookup = rfid_lookup(rfid)
        return next((u for u in self._users.values() if u.rfid_lookup == lookup), None)

    async def get_multi(self, filters: UserFilterDto) -> tuple[int, list[User]]:
        users = list(self._users.values())
        total = len(users)
        if filters.skip:
            users = users[filters.skip :]
        if filters.limit:
            users = users[: filters.limit]
        return total, users

    async def save(self, user: User) -> User:
        if user.id == 0:
            user.id = self._next_id
            self._next_id += 1
        self._users[user.id] = user
        return user

    async def delete(self, user: User) -> None:
        self._users.pop(user.id, None)


class FakeMailService:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_welcome(
        self, email, full_name, username, created_by_name, created_by_email, language=None
    ):
        self.sent.append(
            {
                "type": "welcome",
                "email": email,
                "full_name": full_name,
                "username": username,
                "created_by_name": created_by_name,
                "created_by_email": created_by_email,
                "language": language,
            }
        )

    async def send_notification_digest(self, to, full_name, items, language=None):
        pass

    async def send_schedule_error(self, task_name, message):
        pass

    async def send_disc_space_warning(self, used_gb, total_gb):
        pass

    async def send_custom(self, to, subject, html_body, cc=None, reply_to=None):
        pass

    async def send_test_mail(self, to):
        pass


# ── CreateUser tests ──────────────────────────────────────────────────


class FakeEventBus:
    def __init__(self):
        self.published = []

    async def publish(self, event):
        self.published.append(event)


class FakeUserSessionRepository:
    """Records revocations, UpdateUser only ever revokes, never reads."""

    def __init__(self):
        self.revoked_except: list[tuple[int, object]] = []

    async def revoke_all_for_user(self, user_id):
        self.revoked_except.append((user_id, None))
        return 0

    async def revoke_all_for_user_except(self, user_id, keep_public_id):
        self.revoked_except.append((user_id, keep_public_id))
        return 0


class FakeTrustedDeviceRepository:
    def __init__(self):
        self.revoked_for: list[int] = []

    async def revoke_all_for_user(self, user_id):
        self.revoked_for.append(user_id)
        return 0


class FakeUserPdmLinkRepository:
    """Empty stand-in: none of these use cases change PDM links, they only
    read them back for the result's pdm_links field."""

    async def list_by_user(self, user_id):
        return []


class FakeAdminSettingsRepoForCreateUser:
    """Minimal stand-in: CreateUser only ever calls get_general(), for the
    language and date_format fallback of a user created without an
    explicit one, see AdminGeneralSettings.default_language."""

    def __init__(
        self,
        default_language: Language = Language.enGB,
        default_timezone: str = "Europe/Vienna",
        default_date_format: DateFormat = DateFormat.ISO,
    ) -> None:
        self.general = AdminGeneralSettings(
            id=1,
            company_name=None,
            company_legal_name=None,
            company_logo_key=None,
            contact_email=None,
            imprint_url=None,
            privacy_url=None,
            support_url=None,
            product_number_pattern="",
            project_number_pattern="",
            allow_headless_projects=True,
            empty_value_placeholder="-",
            office_launcher_enabled=False,
            office_sharepoint_url="",
            default_language=default_language,
            default_timezone=default_timezone,
            default_date_format=default_date_format,
            currency="EUR",
        )

    async def get_general(self) -> AdminGeneralSettings:
        return self.general


class TestCreateUser:
    def setup_method(self):
        self.repo = FakeUserRepository()
        self.mail = FakeMailService()
        self.settings = FakeAdminSettingsRepoForCreateUser()
        self.use_case = CreateUser(
            user_repo=self.repo,
            mail_service=self.mail,
            hash_fn=aget_hash,
            settings_repo=self.settings,
            uow=FakeUnitOfWork(),
        )
        self.admin = make_user(id=1, username="admin", permissions=Permission.ALL)

    def _cmd(self, **kwargs) -> CreateUserCommand:
        defaults = dict(
            username="newuser",
            full_name="New User",
            email="new@example.com",
            password="thecakeisalie",
        )
        defaults.update(kwargs)
        return CreateUserCommand(**defaults)

    async def test_user_with_write_users_can_create(self):
        result = await self.use_case.execute(actor=self.admin, cmd=self._cmd())
        assert result.username == "newuser"
        assert result.id > 0

    async def test_auth_provider_is_persisted(self):
        """The command's auth_provider reaches the entity, so a new account
        can be born directory-backed without a second save."""
        result = await self.use_case.execute(
            actor=self.admin, cmd=self._cmd(auth_provider=AuthProvider.LDAP, password=None)
        )
        assert result.auth_provider == AuthProvider.LDAP

    async def test_a_directory_user_is_created_without_a_password(self):
        await self.use_case.execute(
            actor=self.admin, cmd=self._cmd(auth_provider=AuthProvider.LDAP, password=None)
        )

        stored = await self.repo.get_by_username("newuser")
        assert is_unusable_hash(stored.hashed_password)

    async def test_two_directory_users_do_not_share_a_stored_hash(self):
        """Equal hashes would read as "same password" to anyone with table
        access, which is a claim the sentinel should not make."""
        await self.use_case.execute(
            actor=self.admin, cmd=self._cmd(auth_provider=AuthProvider.LDAP, password=None)
        )
        await self.use_case.execute(
            actor=self.admin,
            cmd=self._cmd(
                username="other",
                email="other@example.com",
                auth_provider=AuthProvider.LDAP,
                password=None,
            ),
        )

        first = await self.repo.get_by_username("newuser")
        second = await self.repo.get_by_username("other")
        assert first.hashed_password != second.hashed_password

    async def test_a_local_user_still_needs_a_password(self):
        with pytest.raises(PasswordCriteriaError):
            await self.use_case.execute(actor=self.admin, cmd=self._cmd(password=None))

    async def test_welcome_mail_names_the_creator_instead_of_the_password(self):
        """The password must never appear in the welcome mail, see
        IMailService.send_welcome's docstring. The new user is expected
        to ask the creator for it out of band instead."""
        await self.use_case.execute(actor=self.admin, cmd=self._cmd(password="s3cr3t-password"))

        (sent,) = self.mail.sent
        assert sent["created_by_name"] == "Test User"
        assert sent["created_by_email"] == "admin@example.com"
        assert "s3cr3t-password" not in sent.values()
        assert "password" not in sent

    async def test_welcome_mail_uses_the_new_user_own_language(self):
        """CreateUser passes language=saved.language, the first link in
        the Localized Mail Templates §1 fallback chain, not the actor's
        (creator's) own language."""
        await self.use_case.execute(actor=self.admin, cmd=self._cmd(language="deAT"))

        (sent,) = self.mail.sent
        assert sent["language"] == "deAT"

    async def test_a_broken_stored_welcome_template_does_not_block_account_creation(self):
        """A malformed admin-edited template raises inside
        SmtpMailService.send_welcome (see test_smtp_mail_service.py's
        TestBrokenStoredTemplateRaises). CreateUser's try/except around
        the send must swallow that, costing a welcome mail, never the
        account itself."""

        class BrokenMailService:
            async def send_welcome(self, **kwargs):
                raise Exception("bad Jinja syntax in the stored template")

        use_case = CreateUser(
            user_repo=self.repo,
            mail_service=BrokenMailService(),
            hash_fn=aget_hash,
            settings_repo=self.settings,
            uow=FakeUnitOfWork(),
        )

        result = await use_case.execute(actor=self.admin, cmd=self._cmd())

        assert result.username == "newuser"
        assert await self.repo.get_by_username("newuser") is not None

    async def test_user_without_permissions_cannot_create(self):
        unprivileged = make_user(id=2, username="unprivileged", permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=unprivileged, cmd=self._cmd())

    async def test_permissions_are_saved_as_provided(self):
        perms = [Permission.WRITE_BOUGHT_ITEMS, Permission.WRITE_ORDERS]
        result = await self.use_case.execute(actor=self.admin, cmd=self._cmd(permissions=perms))
        assert result.permissions == perms

    async def test_duplicate_username_raises(self):
        await self.repo.save(make_user(id=2, username="newuser"))
        with pytest.raises(UsernameAlreadyExistsError):
            await self.use_case.execute(actor=self.admin, cmd=self._cmd(username="newuser"))

    async def test_duplicate_email_raises(self):
        existing = make_user(id=2, username="other")
        existing.email = "new@example.com"
        await self.repo.save(existing)
        with pytest.raises(EmailAlreadyExistsError):
            await self.use_case.execute(actor=self.admin, cmd=self._cmd())

    async def test_cannot_create_a_user_named_system(self):
        """`system` is exempt from directory auth by name, so letting another
        account claim it would be a permanent LDAP bypass."""
        with pytest.raises(ReservedUsernameError):
            await self.use_case.execute(actor=self.admin, cmd=self._cmd(username="system"))

    async def test_reserved_name_check_is_case_and_whitespace_insensitive(self):
        with pytest.raises(ReservedUsernameError):
            await self.use_case.execute(actor=self.admin, cmd=self._cmd(username="  SySTeM "))

    async def test_no_one_can_create_a_systemuser(self):
        """CreateUserCommand does not carry is_systemuser at all, so
        every created user is a normal one, regardless of actor, tested
        here with both an admin and the system user itself."""
        result = await self.use_case.execute(actor=self.admin, cmd=self._cmd())
        assert result.is_systemuser is False

        system_actor = make_user(id=9, username="system", is_systemuser=True)
        result = await self.use_case.execute(
            actor=system_actor,
            cmd=self._cmd(username="another", email="another@example.com"),
        )
        assert result.is_systemuser is False

    async def test_member_ids_ignored_when_not_shared_account(self):
        member = await self.repo.save(make_user(id=2, username="alice"))
        result = await self.use_case.execute(
            actor=self.admin, cmd=self._cmd(is_shared_account=False, member_ids=[member.id])
        )
        assert result.member_ids == []

    async def test_shared_account_with_valid_members_succeeds(self):
        alice = await self.repo.save(make_user(id=2, username="alice"))
        bob = await self.repo.save(make_user(id=3, username="bob"))
        result = await self.use_case.execute(
            actor=self.admin,
            cmd=self._cmd(is_shared_account=True, member_ids=[alice.id, bob.id]),
        )
        assert set(result.member_ids) == {alice.id, bob.id}

    async def test_shared_account_rejects_inactive_member(self):
        inactive = await self.repo.save(make_user(id=2, username="bob", is_active=False))
        with pytest.raises(InvalidSharedAccountMemberError):
            await self.use_case.execute(
                actor=self.admin, cmd=self._cmd(is_shared_account=True, member_ids=[inactive.id])
            )

    async def test_shared_account_rejects_service_account_member(self):
        service = await self.repo.save(make_user(id=2, username="api-bot", is_service_account=True))
        with pytest.raises(InvalidSharedAccountMemberError):
            await self.use_case.execute(
                actor=self.admin, cmd=self._cmd(is_shared_account=True, member_ids=[service.id])
            )

    async def test_shared_account_rejects_another_shared_account_as_member(self):
        other_shared = await self.repo.save(
            make_user(id=2, username="terminal-2", is_shared_account=True)
        )
        with pytest.raises(InvalidSharedAccountMemberError):
            await self.use_case.execute(
                actor=self.admin,
                cmd=self._cmd(is_shared_account=True, member_ids=[other_shared.id]),
            )

    async def test_shared_account_rejects_unknown_member_id(self):
        with pytest.raises(InvalidSharedAccountMemberError):
            await self.use_case.execute(
                actor=self.admin, cmd=self._cmd(is_shared_account=True, member_ids=[9999])
            )

    async def test_omitted_locale_fields_resolve_to_the_configured_tenant_defaults(self):
        """Proves const.py's SERVER_DEFAULT_* is not consulted at all:
        the fake settings repo is seeded with values that differ from every
        one of those constants, so a match can only come from
        settings_repo.get_general()."""
        self.settings = FakeAdminSettingsRepoForCreateUser(
            default_language=Language.deAT,
            default_timezone="Europe/London",
            default_date_format=DateFormat.DMY_DOT,
        )
        self.use_case = CreateUser(
            user_repo=self.repo,
            mail_service=self.mail,
            hash_fn=aget_hash,
            settings_repo=self.settings,
            uow=FakeUnitOfWork(),
        )

        result = await self.use_case.execute(actor=self.admin, cmd=self._cmd())

        assert result.language == "deAT"
        assert result.date_format == "dmy_dot"

    async def test_explicit_locale_fields_override_the_tenant_defaults(self):
        result = await self.use_case.execute(
            actor=self.admin,
            cmd=self._cmd(language="deAT", date_format="mdy_slash"),
        )

        assert result.language == "deAT"
        assert result.date_format == "mdy_slash"

    async def test_start_page_defaults_to_dashboard_with_no_tenant_fallback(self):
        """Unlike language and date_format, start_page has no
        AdminGeneralSettings default column. A bare command always lands
        on StartPage.default(), regardless of what the tenant defaults are
        configured to."""
        result = await self.use_case.execute(actor=self.admin, cmd=self._cmd())
        assert result.start_page == "dashboard"

    async def test_explicit_start_page_is_persisted(self):
        result = await self.use_case.execute(
            actor=self.admin, cmd=self._cmd(start_page="production")
        )
        assert result.start_page == "production"


# ── UserRules: direct rule tests ───────────────────────────────────────


class TestAssertCanDisableTotp:
    """Self-service DELETE /users/me/totp/ is refused for the system
    account even with a correct code, admin reset-totp (CLI) is the only
    reset path for it."""

    def test_an_ordinary_user_may_disable_their_own(self):
        UserRules.assert_can_disable_totp(make_user(is_systemuser=False))

    def test_the_system_user_may_not(self):
        with pytest.raises(SystemUserProtectedError):
            UserRules.assert_can_disable_totp(make_user(is_systemuser=True))


# ── UpdateUser tests ──────────────────────────────────────────────────


class FakePasswordConfirmation:
    """Stands in for PasswordConfirmation: accepts CURRENT_PASSWORD only and
    records every check, so a test can tell whether one was made."""

    def __init__(self) -> None:
        self.checked: list[tuple[int, str | None]] = []

    async def confirm(self, actor, password: str, *, client_ip: str | None):
        self.checked.append((actor.id, client_ip))
        if password != CURRENT_PASSWORD:
            raise PasswordConfirmationFailedError("The password is not correct.")
        return actor


CURRENT_PASSWORD = "the-current-password"


class TestUpdateUser:
    def setup_method(self):
        self.admin = make_user(id=1, username="admin", permissions=Permission.ALL)
        self.normal = make_user(id=2, username="normaluser", permissions=[Permission.WRITE_PAT])
        self.repo = FakeUserRepository(users=[self.admin, self.normal])
        self.bus = FakeEventBus()
        self.sessions = FakeUserSessionRepository()
        self.trusted_devices = FakeTrustedDeviceRepository()
        self.confirmation = FakePasswordConfirmation()
        self.use_case = UpdateUser(
            user_repo=self.repo,
            min_password_length=8,
            hash_fn=aget_hash,
            session_repo=self.sessions,
            trusted_device_repo=self.trusted_devices,
            link_repo=FakeUserPdmLinkRepository(),
            event_bus=self.bus,
            uow=FakeUnitOfWork(),
            password_confirmation=self.confirmation,  # type: ignore[arg-type]
        )

    async def test_admin_can_update_other_user(self):
        cmd = UpdateUserCommand(full_name="Updated Name")
        result = await self.use_case.execute(actor=self.admin, target_id=self.normal.id, cmd=cmd)
        assert result.full_name == "Updated Name"

    async def test_user_can_update_self(self):
        cmd = UpdateUserCommand(full_name="My New Name")
        result = await self.use_case.execute(actor=self.normal, target_id=self.normal.id, cmd=cmd)
        assert result.full_name == "My New Name"

    async def test_user_can_change_own_date_format(self):
        cmd = UpdateUserCommand(date_format="dmy_dot")
        result = await self.use_case.execute(actor=self.normal, target_id=self.normal.id, cmd=cmd)
        assert result.date_format == "dmy_dot"

    async def test_user_can_change_own_start_page(self):
        cmd = UpdateUserCommand(start_page="production")
        result = await self.use_case.execute(actor=self.normal, target_id=self.normal.id, cmd=cmd)
        assert result.start_page == "production"

    async def test_start_page_is_untouched_when_not_supplied(self):
        cmd = UpdateUserCommand(full_name="Only The Name")
        result = await self.use_case.execute(actor=self.normal, target_id=self.normal.id, cmd=cmd)
        assert result.start_page == self.normal.start_page

    async def test_date_format_is_untouched_when_not_supplied(self):
        """A partial update must not reset the preference to the server default."""
        cmd = UpdateUserCommand(full_name="Only The Name")
        result = await self.use_case.execute(actor=self.normal, target_id=self.normal.id, cmd=cmd)
        assert result.date_format == self.normal.date_format

    async def test_normal_user_cannot_escalate_own_permissions(self):
        cmd = UpdateUserCommand(permissions=[Permission.WRITE_SETTINGS])
        result = await self.use_case.execute(actor=self.normal, target_id=self.normal.id, cmd=cmd)
        assert Permission.WRITE_SETTINGS not in result.permissions

    async def test_admin_can_set_auth_provider_on_another_user(self):
        cmd = UpdateUserCommand(auth_provider=AuthProvider.LDAP)
        result = await self.use_case.execute(actor=self.admin, target_id=self.normal.id, cmd=cmd)
        assert result.auth_provider == AuthProvider.LDAP

    async def test_user_cannot_move_themselves_onto_the_directory(self):
        """Silently reverted, matching the other admin-only fields."""
        cmd = UpdateUserCommand(auth_provider=AuthProvider.LDAP)
        result = await self.use_case.execute(actor=self.normal, target_id=self.normal.id, cmd=cmd)
        assert result.auth_provider == AuthProvider.LOCAL

    async def test_ldap_user_cannot_move_themselves_back_to_local(self):
        """The direction that matters: otherwise a directory-managed user
        could switch to a local password they control."""
        self.normal.auth_provider = AuthProvider.LDAP
        await self.repo.save(self.normal)
        cmd = UpdateUserCommand(auth_provider=AuthProvider.LOCAL)
        result = await self.use_case.execute(actor=self.normal, target_id=self.normal.id, cmd=cmd)
        assert result.auth_provider == AuthProvider.LDAP

    async def test_auth_provider_is_untouched_when_not_supplied(self):
        self.normal.auth_provider = AuthProvider.LDAP
        await self.repo.save(self.normal)
        cmd = UpdateUserCommand(full_name="Only The Name")
        result = await self.use_case.execute(actor=self.admin, target_id=self.normal.id, cmd=cmd)
        assert result.auth_provider == AuthProvider.LDAP

    # ── Passwords vs auth_provider ────────────────────────────────────

    async def test_admin_cannot_set_a_password_on_a_directory_user(self):
        self.normal.auth_provider = AuthProvider.LDAP
        await self.repo.save(self.normal)
        cmd = UpdateUserCommand(password="a-new-password")
        with pytest.raises(PasswordNotAllowedError):
            await self.use_case.execute(actor=self.admin, target_id=self.normal.id, cmd=cmd)

    async def test_moving_onto_the_directory_invalidates_the_local_password(self):
        """The old password must stop working at the moment of the switch,
        not whenever this row is next touched."""
        cmd = UpdateUserCommand(auth_provider=AuthProvider.LDAP)
        await self.use_case.execute(actor=self.admin, target_id=self.normal.id, cmd=cmd)

        stored = await self.repo.get_by_id(self.normal.id)
        assert is_unusable_hash(stored.hashed_password)

    async def test_setting_a_password_while_switching_to_the_directory_is_refused(self):
        """Checked against the *resulting* provider, so this cannot sneak a
        working local password onto a directory account by ordering."""
        cmd = UpdateUserCommand(password="a-new-password", auth_provider=AuthProvider.LDAP)
        with pytest.raises(PasswordNotAllowedError):
            await self.use_case.execute(actor=self.admin, target_id=self.normal.id, cmd=cmd)

    async def test_a_directory_user_cannot_keep_a_password_by_self_reverting(self):
        """resolve_permission_flags reverts the provider for a self-update.
        If the password rule ran before that, this request would leave a
        working local password on an account that stays on the directory."""
        self.normal.auth_provider = AuthProvider.LDAP
        await self.repo.save(self.normal)
        cmd = UpdateUserCommand(password="mine-now", auth_provider=AuthProvider.LOCAL)
        with pytest.raises(PasswordNotAllowedError):
            await self.use_case.execute(actor=self.normal, target_id=self.normal.id, cmd=cmd)

    async def test_moving_back_to_local_without_a_password_is_refused(self):
        """The stored hash is still the sentinel, so the save would otherwise
        produce an account nobody can ever sign in to."""
        self.normal.auth_provider = AuthProvider.LDAP
        self.normal.hashed_password = unusable_password_hash()
        await self.repo.save(self.normal)
        cmd = UpdateUserCommand(auth_provider=AuthProvider.LOCAL)
        with pytest.raises(PasswordCriteriaError):
            await self.use_case.execute(actor=self.admin, target_id=self.normal.id, cmd=cmd)

    async def test_moving_back_to_local_with_a_password_succeeds(self):
        self.normal.auth_provider = AuthProvider.LDAP
        self.normal.hashed_password = unusable_password_hash()
        await self.repo.save(self.normal)
        cmd = UpdateUserCommand(auth_provider=AuthProvider.LOCAL, password="a-real-password")
        result = await self.use_case.execute(actor=self.admin, target_id=self.normal.id, cmd=cmd)

        assert result.auth_provider == AuthProvider.LOCAL
        stored = await self.repo.get_by_id(self.normal.id)
        assert verify_hash("a-real-password", stored.hashed_password)

    async def test_editing_an_unrelated_field_on_a_directory_user_needs_no_password(self):
        """Only the transition demands one. An admin must still be able to
        deactivate or rename an account that has no local password."""
        self.normal.auth_provider = AuthProvider.LDAP
        self.normal.hashed_password = unusable_password_hash()
        await self.repo.save(self.normal)
        cmd = UpdateUserCommand(full_name="Renamed Person")
        result = await self.use_case.execute(actor=self.admin, target_id=self.normal.id, cmd=cmd)
        assert result.full_name == "Renamed Person"

    async def test_cannot_rename_a_user_to_the_reserved_system_name(self):
        cmd = UpdateUserCommand(username="system")
        with pytest.raises(ReservedUsernameError):
            await self.use_case.execute(actor=self.admin, target_id=self.normal.id, cmd=cmd)

    async def test_admin_can_grant_permissions_to_other_user(self):
        cmd = UpdateUserCommand(permissions=[Permission.WRITE_BOUGHT_ITEMS])
        result = await self.use_case.execute(actor=self.admin, target_id=self.normal.id, cmd=cmd)
        assert Permission.WRITE_BOUGHT_ITEMS in result.permissions

    async def test_cannot_update_systemuser_from_other_account(self):
        sysuser = make_user(id=3, username="system", is_systemuser=True)
        await self.repo.save(sysuser)
        cmd = UpdateUserCommand(full_name="Hacked")
        with pytest.raises(SystemUserProtectedError):
            await self.use_case.execute(actor=self.admin, target_id=sysuser.id, cmd=cmd)

    async def test_weak_password_raises(self):
        cmd = UpdateUserCommand(password="weak", current_password=CURRENT_PASSWORD)
        with pytest.raises(PasswordCriteriaError):
            await self.use_case.execute(actor=self.normal, target_id=self.normal.id, cmd=cmd)

    async def test_own_password_change_revokes_other_sessions_but_spares_current(self):
        """GitHub semantics: changing your password signs out every *other*
        session; the one that made the change survives via session_id_var."""
        from uuid import uuid4

        from src.modules.platform.infrastructure.logging.context import session_id_var

        current_sid = uuid4()
        token = session_id_var.set(str(current_sid))
        try:
            cmd = UpdateUserCommand(
                password="new-strong-password", current_password=CURRENT_PASSWORD
            )
            await self.use_case.execute(actor=self.normal, target_id=self.normal.id, cmd=cmd)
        finally:
            session_id_var.reset(token)

        assert self.sessions.revoked_except == [(self.normal.id, current_sid)]
        assert self.trusted_devices.revoked_for == [self.normal.id]

    async def test_admin_password_change_revokes_all_of_the_targets_sessions(self):
        """The admin's own session belongs to a different account, the
        target gets no spared session."""
        from src.modules.platform.infrastructure.logging.context import session_id_var

        token = session_id_var.set("11111111-1111-1111-1111-111111111111")
        try:
            cmd = UpdateUserCommand(password="new-strong-password")
            await self.use_case.execute(actor=self.admin, target_id=self.normal.id, cmd=cmd)
        finally:
            session_id_var.reset(token)

        assert self.sessions.revoked_except == [(self.normal.id, None)]
        assert self.trusted_devices.revoked_for == [self.normal.id]

    # ── Current password on an own change ─────────────────────────────

    async def test_an_own_password_change_needs_the_current_password(self):
        cmd = UpdateUserCommand(password="new-strong-password")
        with pytest.raises(CurrentPasswordRequiredError):
            await self.use_case.execute(actor=self.normal, target_id=self.normal.id, cmd=cmd)
        assert self.sessions.revoked_except == []

    async def test_a_wrong_current_password_changes_nothing(self):
        before = self.normal.hashed_password
        cmd = UpdateUserCommand(password="new-strong-password", current_password="wrong")
        with pytest.raises(PasswordConfirmationFailedError):
            await self.use_case.execute(
                actor=self.normal, target_id=self.normal.id, cmd=cmd, client_ip="10.0.0.7"
            )
        assert (await self.repo.get_by_id(self.normal.id)).hashed_password == before
        assert self.confirmation.checked == [(self.normal.id, "10.0.0.7")]

    async def test_the_right_current_password_changes_it(self):
        before = self.normal.hashed_password
        cmd = UpdateUserCommand(password="new-strong-password", current_password=CURRENT_PASSWORD)
        await self.use_case.execute(actor=self.normal, target_id=self.normal.id, cmd=cmd)
        assert (await self.repo.get_by_id(self.normal.id)).hashed_password != before

    async def test_an_admin_setting_someone_elses_password_is_not_asked(self):
        cmd = UpdateUserCommand(password="new-strong-password")
        await self.use_case.execute(actor=self.admin, target_id=self.normal.id, cmd=cmd)
        assert self.confirmation.checked == []

    async def test_an_admin_changing_their_own_password_is_asked(self):
        cmd = UpdateUserCommand(password="new-strong-password")
        with pytest.raises(CurrentPasswordRequiredError):
            await self.use_case.execute(actor=self.admin, target_id=self.admin.id, cmd=cmd)

    async def test_a_directory_user_is_refused_before_being_asked(self):
        self.normal.auth_provider = AuthProvider.LDAP
        await self.repo.save(self.normal)
        cmd = UpdateUserCommand(password="new-strong-password", current_password="x")
        with pytest.raises(PasswordNotAllowedError):
            await self.use_case.execute(actor=self.normal, target_id=self.normal.id, cmd=cmd)
        assert self.confirmation.checked == []

    async def test_other_own_changes_need_no_current_password(self):
        cmd = UpdateUserCommand(full_name="Still Me", password="")
        await self.use_case.execute(actor=self.normal, target_id=self.normal.id, cmd=cmd)
        assert self.confirmation.checked == []

    async def test_non_password_update_revokes_nothing(self):
        cmd = UpdateUserCommand(full_name="Still Me")
        await self.use_case.execute(actor=self.normal, target_id=self.normal.id, cmd=cmd)
        assert self.sessions.revoked_except == []
        assert self.trusted_devices.revoked_for == []

    async def test_duplicate_username_raises(self):
        await self.repo.save(make_user(id=3, username="taken"))
        cmd = UpdateUserCommand(username="taken")
        with pytest.raises(UsernameAlreadyExistsError):
            await self.use_case.execute(actor=self.admin, target_id=self.normal.id, cmd=cmd)

    async def test_target_not_found_raises(self):
        cmd = UpdateUserCommand(full_name="Ghost")
        with pytest.raises(UserNotFoundError):
            await self.use_case.execute(actor=self.admin, target_id=9999, cmd=cmd)

    async def test_admin_can_assign_valid_members_to_shared_account(self):
        terminal = await self.repo.save(
            make_user(id=3, username="terminal", is_shared_account=True)
        )
        cmd = UpdateUserCommand(member_ids=[self.normal.id])
        result = await self.use_case.execute(actor=self.admin, target_id=terminal.id, cmd=cmd)
        assert result.member_ids == [self.normal.id]

    async def test_admin_cannot_assign_invalid_member_to_shared_account(self):
        terminal = await self.repo.save(
            make_user(id=3, username="terminal", is_shared_account=True)
        )
        inactive = await self.repo.save(make_user(id=4, username="ghost", is_active=False))
        cmd = UpdateUserCommand(member_ids=[inactive.id])
        with pytest.raises(InvalidSharedAccountMemberError):
            await self.use_case.execute(actor=self.admin, target_id=terminal.id, cmd=cmd)

    async def test_shared_account_cannot_list_itself_as_member(self):
        terminal = await self.repo.save(
            make_user(id=3, username="terminal", is_shared_account=True)
        )
        cmd = UpdateUserCommand(member_ids=[terminal.id])
        with pytest.raises(InvalidSharedAccountMemberError):
            await self.use_case.execute(actor=self.admin, target_id=terminal.id, cmd=cmd)

    async def test_turning_off_shared_account_clears_members(self):
        terminal = await self.repo.save(
            make_user(
                id=3, username="terminal", is_shared_account=True, member_ids=[self.normal.id]
            )
        )
        cmd = UpdateUserCommand(is_shared_account=False)
        result = await self.use_case.execute(actor=self.admin, target_id=terminal.id, cmd=cmd)
        assert result.member_ids == []

    async def test_self_edit_cannot_change_own_shared_account_flag_or_members(self):
        terminal = await self.repo.save(
            make_user(id=3, username="terminal", is_shared_account=True, member_ids=[])
        )
        cmd = UpdateUserCommand(is_shared_account=False, member_ids=[self.normal.id])
        result = await self.use_case.execute(actor=terminal, target_id=terminal.id, cmd=cmd)
        assert result.is_shared_account is True
        assert result.member_ids == []


# ── AuthenticateUser tests ────────────────────────────────────────────


class TestAuthenticateUser:
    def setup_method(self):
        self.user = make_user(id=1, username="alice", password="correctpassword")
        self.repo = FakeUserRepository(users=[self.user])
        self.use_case = AuthenticateUser(self.repo, verify_fn=averify_hash)

    async def test_correct_credentials_return_user(self):
        result = await self.use_case.by_password("alice", "correctpassword")
        assert result.id == 1

    async def test_wrong_password_raises(self):
        with pytest.raises(UserNotFoundError):
            await self.use_case.by_password("alice", "wrongpassword")

    async def test_unknown_username_raises(self):
        with pytest.raises(UserNotFoundError):
            await self.use_case.by_password("nobody", "anything")

    async def test_inactive_user_raises(self):
        inactive = make_user(id=2, username="inactive", is_active=False, password="pass1234")
        await self.repo.save(inactive)
        with pytest.raises(InactiveUserError):
            await self.use_case.by_password("inactive", "pass1234")


# ── GetUser / GetUsers tests ──────────────────────────────────────────


class TestGetUser:
    def setup_method(self):
        self.users = [make_user(id=i, username=f"user{i}") for i in range(1, 4)]
        self.repo = FakeUserRepository(users=self.users)
        self.links = FakeUserPdmLinkRepository()
        self.admin = make_user(id=100, username="admin", permissions=[Permission.READ_SETTINGS])

    async def test_get_existing_user(self):
        result = await GetUser(self.repo, self.links).execute(actor=self.admin, user_id=1)
        assert result.username == "user1"

    async def test_get_nonexistent_user_raises(self):
        with pytest.raises(UserNotFoundError):
            await GetUser(self.repo, self.links).execute(actor=self.admin, user_id=999)

    async def test_get_all_users(self):
        result = await GetUsers(self.repo, self.links).execute(
            actor=self.admin, filters=UserFilterDto()
        )
        assert result.total == 3
        assert len(result.items) == 3

    async def test_get_users_with_limit(self):
        result = await GetUsers(self.repo, self.links).execute(
            actor=self.admin, filters=UserFilterDto(limit=2)
        )
        assert len(result.items) == 2


# ── AuthenticateUser with a directory ─────────────────────────────────


class FakeLdapAuthenticator:
    """Scripted directory. `verdict` is True/False for accept/reject, or an
    exception instance to raise."""

    def __init__(self, verdict: bool | Exception = True) -> None:
        self.verdict = verdict
        self.calls: list[tuple[str, str]] = []

    async def authenticate(self, username: str, password: str) -> bool:
        self.calls.append((username, password))
        if isinstance(self.verdict, Exception):
            raise self.verdict
        return self.verdict


class SpyVerify:
    """Wraps averify_hash so tests can assert the local hash was never
    consulted."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, plain: str, hashed: str) -> bool:
        self.calls += 1
        return await averify_hash(plain, hashed)


async def test_password_login_ends_the_read_transaction_before_hashing():
    events = []
    user = make_user(id=1, username="alice", password="local-password")

    class RecordingUow:
        async def commit(self):
            events.append("commit")

        async def rollback(self):
            events.append("rollback")

    async def verify(plain, hashed):
        events.append("verify")
        return await averify_hash(plain, hashed)

    use_case = AuthenticateUser(
        FakeUserRepository(users=[user]), verify_fn=verify, uow=RecordingUow()
    )

    assert await use_case.by_password("alice", "local-password") == user
    assert events == ["commit", "verify"]


class TestAuthenticateUserWithLdap:
    def setup_method(self):
        self.user = make_user(id=1, username="alice", password="local-password")
        self.user.auth_provider = AuthProvider.LDAP
        self.repo = FakeUserRepository(users=[self.user])
        self.verify = SpyVerify()

    def _use_case(self, ldap):
        return AuthenticateUser(
            self.repo,
            verify_fn=self.verify,
            ldap=ldap,
            ldap_enabled=True,
        )

    # ── The security core ─────────────────────────────────────────────

    async def test_ldap_rejection_does_not_fall_back_to_the_local_password(self):
        """THE test. The directory was reached and said no, while the local
        password happens to be correct. Falling back here would let a stale
        hash outlive a disabled or rotated directory account."""
        ldap = FakeLdapAuthenticator(False)

        with pytest.raises(UserNotFoundError):
            await self._use_case(ldap).by_password("alice", "local-password")

        assert self.verify.calls == 0, "the local hash must never be consulted"

    async def test_connection_error_rejects_rather_than_falling_back(self):
        """The accepted cost of holding no copy of the directory password:
        an unreachable DC means nobody it answers for can sign in."""
        ldap = FakeLdapAuthenticator(LdapUnavailableError("dc unreachable"))

        with pytest.raises(UserNotFoundError):
            await self._use_case(ldap).by_password("alice", "local-password")

        assert self.verify.calls == 0, "the local hash must never be consulted"

    async def test_connection_error_with_a_wrong_password_still_rejects(self):
        ldap = FakeLdapAuthenticator(LdapUnavailableError("dc unreachable"))

        with pytest.raises(UserNotFoundError):
            await self._use_case(ldap).by_password("alice", "not-the-password")

    async def test_ldap_errors_never_escape_the_use_case(self):
        """A 503 on this public endpoint would be an availability oracle and,
        with the fast 401 for unknown names, a user-enumeration oracle."""
        ldap = FakeLdapAuthenticator(LdapUnavailableError("dc unreachable"))
        self.user.hashed_password = "not-a-bcrypt-hash"

        with pytest.raises(UserNotFoundError):
            await self._use_case(ldap).by_password("alice", "anything")

    async def test_a_directory_outage_raises_the_unverifiable_subtype(self):
        """The outage must be distinguishable from a wrong password so
        the caller (web_login) can skip counting it toward lockout, while
        every existing `except UserNotFoundError`/`pytest.raises` still
        catches it unchanged, because it is a subclass."""
        ldap = FakeLdapAuthenticator(LdapUnavailableError("dc unreachable"))

        with pytest.raises(CredentialsUnverifiableError) as excinfo:
            await self._use_case(ldap).by_password("alice", "local-password")

        assert isinstance(excinfo.value, UserNotFoundError)

    async def test_a_successful_bind_writes_nothing_back(self):
        """No cache means no copy of the directory password lands in our
        database, on this path or any other."""
        original_hash = self.user.hashed_password

        await self._use_case(FakeLdapAuthenticator(True)).by_password("alice", "the-ad-password")

        assert self.user.hashed_password == original_hash
        assert self.verify.calls == 0

    # ── The unusable sentinel ─────────────────────────────────────────

    async def test_a_sentinel_hash_is_never_accepted_locally(self):
        """A provisioned directory account routed to the local path, because
        LDAP was switched off globally. It must not become a way in: bcrypt
        would raise on the sentinel, and an unhandled raise here is a 500 on
        a public endpoint rather than a 401."""
        self.user.hashed_password = unusable_password_hash()
        use_case = AuthenticateUser(self.repo, verify_fn=self.verify, ldap_enabled=False)

        with pytest.raises(UserNotFoundError):
            await use_case.by_password("alice", "anything")

        assert self.verify.calls == 0

    async def test_the_sentinel_is_refused_even_for_its_own_literal_value(self):
        """The random tail is not a secret, so someone who read it out of the
        database must still not be able to present it as a password."""
        sentinel = unusable_password_hash()
        self.user.hashed_password = sentinel
        use_case = AuthenticateUser(self.repo, verify_fn=self.verify, ldap_enabled=False)

        with pytest.raises(UserNotFoundError):
            await use_case.by_password("alice", sentinel)

    # ── Routing: who reaches the directory at all ─────────────────────

    async def test_binds_with_the_resolved_username_not_the_typed_identifier(self):
        ldap = FakeLdapAuthenticator(True)

        await self._use_case(ldap).by_password("alice@example.com", "pw")

        assert ldap.calls == [("alice", "pw")]

    async def test_a_local_provider_user_never_reaches_the_directory(self):
        self.user.auth_provider = AuthProvider.LOCAL
        ldap = FakeLdapAuthenticator(True)

        await self._use_case(ldap).by_password("alice", "local-password")

        assert ldap.calls == []

    async def test_the_system_user_never_reaches_the_directory(self):
        system = make_user(id=2, username="system", password="sys-password")
        system.auth_provider = AuthProvider.LDAP
        await self.repo.save(system)
        ldap = FakeLdapAuthenticator(False)

        assert (await self._use_case(ldap).by_password("system", "sys-password")).id == 2
        assert ldap.calls == []

    async def test_an_empty_password_never_reaches_the_directory(self):
        ldap = FakeLdapAuthenticator(True)

        with pytest.raises(UserNotFoundError):
            await self._use_case(ldap).by_password("alice", "")

        assert ldap.calls == []

    async def test_a_service_account_never_reaches_the_directory(self):
        self.user.is_service_account = True
        ldap = FakeLdapAuthenticator(True)

        with pytest.raises(UserNotFoundError):
            await self._use_case(ldap).by_password("alice", "local-password")

        assert ldap.calls == []

    async def test_an_unknown_identifier_never_reaches_the_directory(self):
        ldap = FakeLdapAuthenticator(True)

        with pytest.raises(UserNotFoundError):
            await self._use_case(ldap).by_password("nobody", "pw")

        assert ldap.calls == []

    async def test_ldap_globally_disabled_uses_the_local_password(self):
        ldap = FakeLdapAuthenticator(False)
        use_case = AuthenticateUser(self.repo, verify_fn=self.verify, ldap=ldap, ldap_enabled=False)

        assert (await use_case.by_password("alice", "local-password")).id == 1
        assert ldap.calls == []

    # ── Account state ─────────────────────────────────────────────────

    async def test_inactive_user_raises_after_a_successful_bind(self):
        self.user.is_active = False
        ldap = FakeLdapAuthenticator(True)

        with pytest.raises(InactiveUserError):
            await self._use_case(ldap).by_password("alice", "pw")
