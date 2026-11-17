"""Owns the SOLIDWORKS PDM Web API session lifecycle: reuse the stored bearer
token when it is still fresh, authenticate when there is none or it has
aged past SESSION_MAX_AGE, and retry once on a 401, or on a 503 for a
reused token, that could not have been predicted from the token's age
alone (the vault restarted, or PDM closed the underlying server-side
Session for another reason; the Web API reports the latter as an empty
503, not a 401).

The token lives on the settings row rather than per worker or in Redis,
because each authenticate opens a server-side session that likely holds a
license seat and has no expiry or logout, so every worker shares one. All
Web API use goes through PdmSessionService.call.

With a unit of work wired, `call` commits it before every Web API request
it makes, authenticate included, so no pooled connection sits in an open
transaction for an HTTP wait that can last up to the configured timeout.
A newly obtained or cleared session token commits straight away, before
the caller writes anything else, because PDM has already opened (or
dropped) the server-side session every worker shares and a caller that
later rolls back must not undo that. A fresh token rides on the commit
`call` makes right after authenticating; a cleared one commits on its own
before the authentication error propagates.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import timedelta
from typing import TypeVar

from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.errors import PdmApiError
from src.modules.external_data.domain.errors import PdmAuthenticationFailedError
from src.modules.external_data.domain.errors import PdmNotConfiguredError
from src.modules.external_data.domain.errors import PdmSessionExpiredError
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGateway
from src.modules.external_data.ports.outbound.pdm_gateway_port import IPdmGatewayFactory
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConnection
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc

T = TypeVar("T")

# A safety bound only; the retry in `call` catches a dead token earlier, and
# a shorter cap would just burn license seats.
SESSION_MAX_AGE = timedelta(hours=24)

# The Web API answers an empty 503 for a token whose session it dropped,
# indistinguishable from an outage, so `call` only retries it for a reused
# token.
_DROPPED_SESSION_STATUS_CODE = 503


class PdmSessionService:
    def __init__(
        self,
        repo: IExternalDataSettingsRepository,
        gateway_factory: IPdmGatewayFactory,
        uow: IUnitOfWork | None = None,
    ) -> None:
        self._repo = repo
        self._gateway_factory = gateway_factory
        self._uow = uow

    async def _release_connection(self) -> None:
        """Ends the session's open transaction before a Web API request.
        This is safe because no caller has pending writes at `call`, so the
        only thing it can persist besides ending the read transaction is a
        session token `_authenticate` has just stored."""
        if self._uow is not None:
            await self._uow.commit()

    async def call(self, fn: Callable[[IPdmGateway, str], Awaitable[T]]) -> T:
        """Run `fn(gateway, token)` against the saved connection and a
        usable bearer token.

        Raises PdmNotConfiguredError when the saved connection is
        incomplete. Reuses the stored token unless it is missing or older
        than SESSION_MAX_AGE, in which case it authenticates first and
        persists the result. If `fn` raises PdmSessionExpiredError (the
        gateway's internal 401 signal), authenticates again, persists the
        new token, and retries `fn` once; a second failure propagates
        unchanged. A PdmApiError with status 503 on a reused (not freshly
        obtained) token is treated the same way, since that is how the Web
        API reports a session it dropped on its side. If an authenticate
        attempt (initial or retry) raises PdmAuthenticationFailedError, the
        stored session is cleared before the error is re-raised, so a
        rejected token is never reused.
        """
        settings = await self._repo.get_pdm()
        if not settings.is_configured:
            raise PdmNotConfiguredError("The PDM connection is not fully configured.")

        connection = PdmConnection(
            base_url=settings.base_url,
            vault_name=settings.vault_name,
            verify_certificate=settings.verify_certificate,
            timeout_seconds=settings.timeout_seconds,
        )
        gateway = self._gateway_factory(connection)
        token, reused = await self._resolve_token(settings, gateway)

        await self._release_connection()
        try:
            return await fn(gateway, token)
        except PdmSessionExpiredError:
            token = await self._authenticate(gateway, settings.username, settings.password or "")
            await self._release_connection()
            return await fn(gateway, token)
        except PdmApiError as exc:
            # The Web API answers 503 with an empty body, not 401, for a
            # session it has dropped on its side (idle timeout, server
            # restart), so a reused token that has gone bad this way never
            # raises PdmSessionExpiredError. Treat a 503 on a reused token
            # exactly like a 401: log in again and retry once. A 503 on a
            # token obtained in this very call is a real outage and
            # propagates.
            if exc.status_code != _DROPPED_SESSION_STATUS_CODE or not reused:
                raise
            log.info("PDM answered 503 on a reused session token; re-authenticating once.")
            token = await self._authenticate(gateway, settings.username, settings.password or "")
            await self._release_connection()
            return await fn(gateway, token)

    async def _resolve_token(
        self, settings: AdminPdmSettings, gateway: IPdmGateway
    ) -> tuple[str, bool]:
        """The bearer token to make this call with, and whether it was
        reused from storage rather than freshly obtained just now. The
        caller's own 503 retry only makes sense for a reused token (see
        `call`'s docstring). Authenticates when there is no stored token,
        or it has aged past SESSION_MAX_AGE."""
        stored_token = settings.session_token
        obtained_at = settings.session_obtained_at
        stale = (
            stored_token is None or obtained_at is None or now_utc() - obtained_at > SESSION_MAX_AGE
        )
        if stale:
            return await self._authenticate(
                gateway, settings.username, settings.password or ""
            ), False
        assert stored_token is not None  # `stale` is False only when a token is stored
        return stored_token, True

    async def _authenticate(self, gateway: IPdmGateway, username: str, password: str) -> str:
        await self._release_connection()
        try:
            result = await gateway.authenticate(username, password)
        except PdmAuthenticationFailedError:
            await self._repo.save_pdm_session(token=None, user_id=None, obtained_at=None)
            if self._uow is not None:
                await self._uow.commit()
            raise
        obtained_at = now_utc()
        await self._repo.save_pdm_session(
            token=result.token, user_id=result.user_id, obtained_at=obtained_at
        )
        return result.token
