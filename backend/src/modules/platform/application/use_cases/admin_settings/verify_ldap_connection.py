"""
Probes a directory with settings that have not been saved yet, so an admin can
validate a configuration before switching it on for everyone.

Named Verify rather than Test because pytest collects `Test*` classes and would
otherwise emit a collection warning wherever this is imported.

Because binding is done as the end user (no service account), the probe needs a
real credential: the admin supplies their own directory account. It is never
stored and never logged.
"""

from src.modules.platform.application.dto.admin_settings_dto.auth import VerifyLdapConnectionCommand
from src.modules.platform.domain.entities.admin_settings.auth import AdminAuthSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import LdapAuthenticationFailedError
from src.modules.platform.domain.exceptions import LdapNotConfiguredError
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.ldap_authenticator_port import ILdapAuthenticatorFactory
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class VerifyLdapConnection:
    def __init__(
        self, ldap_factory: ILdapAuthenticatorFactory, uow: IUnitOfWork | None = None
    ) -> None:
        self._ldap_factory = ldap_factory
        self._uow = uow

    async def execute(self, actor: User, cmd: VerifyLdapConnectionCommand) -> None:
        """Returns None on a successful bind.

        Raises LdapNotConfiguredError when the probe cannot even be attempted,
        LdapAuthenticationFailedError when the directory answered "no", and
        lets LdapUnavailableError through when it could not be reached. Those
        three are exactly the verdicts an admin needs to tell apart.
        """
        SettingsRules.assert_can_write(actor)

        if not cmd.username.strip():
            raise LdapNotConfiguredError("A username is required to test the bind.")
        if not cmd.password:
            raise LdapNotConfiguredError("A password is required to test the bind.")

        target = AdminAuthSettings(
            id=1,
            # Probe regardless of the stored switch, the whole point is to
            # validate the configuration *before* enabling it.
            ldap_enabled=True,
            ldap_host=cmd.ldap_host.strip(),
            ldap_port=cmd.ldap_port,
            ldap_use_ssl=cmd.ldap_use_ssl,
            ldap_start_tls=cmd.ldap_start_tls,
            ldap_verify_certificate=cmd.ldap_verify_certificate,
            ldap_domain=cmd.ldap_domain.strip(),
            ldap_timeout_seconds=cmd.ldap_timeout_seconds,
        )

        # Nothing is written here; free the connection for the bind, which
        # may wait up to the configured LDAP timeout.
        if self._uow is not None:
            await self._uow.commit()
        if not await self._ldap_factory(target).authenticate(cmd.username.strip(), cmd.password):
            raise LdapAuthenticationFailedError(
                "Reached the directory, but it rejected those credentials."
            )

        log.info("LDAP connection test succeeded.")
