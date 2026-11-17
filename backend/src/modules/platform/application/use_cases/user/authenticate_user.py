"""Password authentication; returns the user and leaves the token to the
caller.

A directory account has no local credential, only an unusable sentinel
hash, so a rejected and an unreachable directory both reject the login.
That availability cost is deliberate, because the alternative is caching
directory passwords locally. The `system` account stays local and is the
way in when the directory is down.
"""

from collections.abc import Awaitable
from collections.abc import Callable

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import CredentialsUnverifiableError
from src.modules.platform.domain.exceptions import InactiveUserError
from src.modules.platform.domain.exceptions import LdapUnavailableError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.login_policy import resolves_to_ldap
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.security.hashing import is_unusable_hash
from src.modules.platform.ports.outbound.ldap_authenticator_port import ILdapAuthenticator
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc


class AuthenticateUser:
    def __init__(
        self,
        user_repo: IUserRepository,
        verify_fn: Callable[[str, str], Awaitable[bool]],
        ldap: ILdapAuthenticator | None = None,
        ldap_enabled: bool = False,
        uow: IUnitOfWork | None = None,
    ) -> None:
        self._repo = user_repo
        self._verify = verify_fn
        self._ldap = ldap
        self._ldap_enabled = ldap_enabled
        self._uow = uow
        # The account the last by_password call named, whether or not its
        # password was right, so a refused login can name it in the
        # security log. None when the name matched no usable account.
        self.candidate: User | None = None

    async def by_password(self, identifier: str, password: str) -> User:
        """Validates a username or e-mail plus password.

        An unreachable directory raises CredentialsUnverifiableError, a 401
        that does not count as a failed guess. No LDAP exception may escape,
        because on this public endpoint a 503 would reveal availability and,
        by timing, which usernames exist.
        """
        user = await self._repo.get_by_username_or_email(identifier)
        self.candidate = user if user is not None and not user.is_service_account else None
        if not user or user.is_service_account or not password:
            log.warning("Failed password login attempt for identifier %r.", identifier)
            raise UserNotFoundError("Incorrect username or password.")

        # Nothing has been written yet. Ending the read transaction hands the
        # connection back to the pool for the bcrypt check or directory bind,
        # which take far longer than any query in this request.
        if self._uow is not None:
            await self._uow.commit()

        if self._ldap is None or not resolves_to_ldap(user, self._ldap_enabled):
            await self._verify_local(user, password, identifier)
        else:
            await self._verify_directory(user, password, identifier)

        if not user.is_active:
            log.warning("Login blocked, inactive account: %r (id=%s).", user.username, user.id)
            raise InactiveUserError("Account is inactive.")
        return user

    async def _verify_directory(self, user: User, password: str, identifier: str) -> None:
        """Bind against the directory. It is the only authority for this
        account, so neither of its failure modes falls back to anything."""
        assert self._ldap is not None  # guarded by the caller
        try:
            # The resolved username, since the identifier may be an e-mail.
            accepted = await self._ldap.authenticate(user.username, password)
        except LdapUnavailableError as exc:
            # Logged as an outage but answered like a wrong password; the
            # subtype keeps it out of the lockout count.
            log.warning(
                "LDAP unreachable during login for %r (id=%s): %s", user.username, user.id, exc
            )
            raise CredentialsUnverifiableError("Incorrect username or password.") from None

        if not accepted:
            log.warning("LDAP rejected the credentials for %r (id=%s).", user.username, user.id)
            raise UserNotFoundError("Incorrect username or password.")

        log.info("User %r (id=%s) authenticated via LDAP.", user.username, user.id)

    async def _verify_local(self, user: User, password: str, identifier: str) -> None:
        """Check the locally stored bcrypt hash. Raises UserNotFoundError on
        any mismatch."""
        if is_unusable_hash(user.hashed_password):
            # A directory-provisioned account reaching this path: either LDAP
            # was switched off globally, or the account was moved back to
            # local without a password being set. Neither may become a way in.
            log.warning(
                "User %r (id=%s) has no local password (auth_provider=%r).",
                user.username,
                user.id,
                user.auth_provider,
            )
            raise UserNotFoundError("Incorrect username or password.")
        try:
            ok = await self._verify(password, user.hashed_password)
        except ValueError:
            # Backstop for a genuinely corrupt digest. The sentinel is caught
            # above; this only fires on a value that is neither, and an
            # unhandled ValueError on the login endpoint is a 500, not a 401.
            log.warning(
                "User %r (id=%s) has an unusable local password hash.", user.username, user.id
            )
            ok = False
        if not ok:
            log.warning("Failed password login attempt for identifier %r.", identifier)
            raise UserNotFoundError("Incorrect username or password.")
        log.info("User %r (id=%s) authenticated via password.", user.username, user.id)

    @staticmethod
    async def complete_login(repo: IUserRepository, user: User) -> User:
        """Stamps last_logged_in without committing. Call only once a login
        fully succeeded, not on a pending 2FA step or an RFID lookup."""
        user.last_logged_in = now_utc()
        return await repo.save(user)
