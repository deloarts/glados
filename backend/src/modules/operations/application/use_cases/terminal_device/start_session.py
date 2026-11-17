"""
The last step of a device sign-in: checks the signed challenge and returns a
short-lived terminal access token together with the device's state.

The nonce must have been issued for this public key, must not have expired
and is claimed in the replay guard, so it works once across every worker.
The signature must verify under the public key. A known key needs nothing
else, so revoking or rotating terminal keys never cuts off an enrolled
display. An unknown key needs a valid terminal key in `X-Api-Key` and is
registered as a pending terminal with a pairing code, unless the pending cap
is reached. A revoked display that signs in again goes back to pending with
a new code. A session for another address while the previous token is still
valid marks the terminal as possibly cloned.

Every session records the telemetry the page sends, the hardware details of
the bridge included. Those come from the device and are cleaned by the
domain parser rather than refused, so a display with an odd report still
signs in.
"""

import hashlib
from datetime import datetime

from src.modules.operations.application.dto.terminal_dto import StartTerminalSessionCommand
from src.modules.operations.application.dto.terminal_dto import TerminalSessionResult
from src.modules.operations.application.services.terminal_audit import record_terminal_audit
from src.modules.operations.application.services.terminal_auth_rate_limiter import (
    TerminalAuthRateLimiter,
)
from src.modules.operations.application.services.terminal_device_state import (
    TerminalDeviceStateReader,
)
from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.errors import InvalidTerminalKeyError
from src.modules.operations.domain.errors import NotATerminalKeyError
from src.modules.operations.domain.errors import TerminalChallengeError
from src.modules.operations.domain.errors import TerminalKeyRequiredError
from src.modules.operations.domain.errors import TerminalSignatureError
from src.modules.operations.domain.services import terminal_rules
from src.modules.operations.domain.value_objects.terminal import STALE_PENDING_AFTER
from src.modules.operations.domain.value_objects.terminal import TERMINAL_CHALLENGE_TTL_SECONDS
from src.modules.operations.domain.value_objects.terminal import TERMINAL_TOKEN_TTL
from src.modules.operations.domain.value_objects.terminal import TerminalMode
from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.operations.domain.value_objects.terminal_device_details import parse_device_details
from src.modules.operations.infrastructure.security.terminal_auth import (
    create_terminal_access_token,
)
from src.modules.operations.infrastructure.security.terminal_auth import nonce_valid_for
from src.modules.operations.infrastructure.security.terminal_auth import public_key_fingerprint
from src.modules.operations.infrastructure.security.terminal_auth import signature_valid
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.repositories.terminal_repository import (
    ITerminalRepository,
)
from src.modules.platform.application.services.validate_api_key import ValidateApiKey
from src.modules.platform.domain.exceptions import InactiveUserError
from src.modules.platform.domain.exceptions import InvalidTokenError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.services.token_permission_rules import TERMINAL_KEY_SCOPES
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.infrastructure.security.api_key import hash_api_key
from src.modules.platform.ports.outbound.replay_guard_port import IReplayGuard
from src.modules.platform.ports.outbound.repositories.api_key_repository import IApiKeyRepository
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import now_utc

# Outlives the nonce itself, so a nonce cannot be claimed again in the
# seconds around its expiry.
_NONCE_CLAIM_SECONDS = TERMINAL_CHALLENGE_TTL_SECONDS + 30


class StartTerminalSession:
    def __init__(
        self,
        terminal_repo: ITerminalRepository,
        settings_repo: IOperationsSettingsRepository,
        key_repo: IApiKeyRepository,
        user_repo: IUserRepository,
        replay_guard: IReplayGuard,
        rate_limiter: TerminalAuthRateLimiter,
        state_reader: TerminalDeviceStateReader,
        uow: IUnitOfWork,
    ) -> None:
        self._terminals = terminal_repo
        self._settings = settings_repo
        self._keys = key_repo
        self._users = user_repo
        self._replay_guard = replay_guard
        self._limiter = rate_limiter
        self._state = state_reader
        self._uow = uow

    async def execute(self, cmd: StartTerminalSessionCommand) -> TerminalSessionResult:
        terminal_rules.assert_access_allowed(await self._settings.get_security(), cmd.client_ip)
        self._limiter.check("session", cmd.client_ip)
        now = now_utc()

        if not nonce_valid_for(cmd.nonce, cmd.public_key, now):
            raise TerminalChallengeError("The challenge is unknown, expired or for another key.")
        if not signature_valid(cmd.public_key, cmd.nonce, cmd.signature):
            raise TerminalSignatureError("The signature over the challenge does not verify.")
        nonce_digest = hashlib.sha256(cmd.nonce.encode("ascii")).hexdigest()
        if not await self._replay_guard.consume_once(
            f"terminal-nonce:{nonce_digest}", _NONCE_CLAIM_SECONDS
        ):
            raise TerminalChallengeError("The challenge was already used.")

        known = await self._terminals.get_by_public_key(cmd.public_key)
        # A known terminal is read again under its row lock, so a revoke or
        # approval that commits while this request runs is not overwritten.
        terminal = await self._terminals.lock_for_update(known.id) if known else None
        if terminal is None:
            terminal = await self._register(cmd, now)
        else:
            await self._refresh_known(terminal, now)

        self._record_telemetry(terminal, cmd, now)
        clone = terminal_rules.detect_clone(terminal, cmd.client_ip, now)
        saved = await self._terminals.save(terminal)
        if clone:
            log.warning(
                f"Terminal #{saved.id} ({saved.public_key_fingerprint}) started a session from "
                f"{cmd.client_ip} while a token issued to another address was still valid; "
                "its key may have been copied."
            )
            await record_terminal_audit(
                self._settings,
                None,
                f"Possible clone of terminal #{saved.id} ({saved.public_key_fingerprint}): "
                f"session from {cmd.client_ip} while another address held a valid token.",
            )
        await self._uow.commit()

        token, expires_at = create_terminal_access_token(saved.id, now, TERMINAL_TOKEN_TTL)
        return TerminalSessionResult(
            access_token=token,
            expires_at=expires_at,
            state=await self._state.read(saved),
        )

    async def _register(self, cmd: StartTerminalSessionCommand, now: datetime) -> Terminal:
        """A pending terminal for an unknown key, which needs a terminal key."""
        api_key_id = await self._check_terminal_key(cmd.api_key)
        removed = await self._terminals.delete_stale_pending(now - STALE_PENDING_AFTER)
        if removed:
            log.info(f"Removed {removed} pending terminal(s) whose pairing code expired long ago.")
        terminal_rules.assert_pending_capacity(await self._terminals.count_active_pending(now))
        terminal = Terminal(
            id=0,
            public_key=cmd.public_key,
            public_key_fingerprint=public_key_fingerprint(cmd.public_key),
            status=TerminalStatus.PENDING,
            mode=TerminalMode.default(),
            name=None,
            pairing_code=None,
            pairing_expires_at=None,
            infoscreen_id=None,
            api_key_id=api_key_id,
            first_seen_at=now,
            last_seen_at=now,
            created=now,
        )
        terminal_rules.issue_pairing_code(
            terminal, await self._terminals.get_pending_pairing_codes(), now
        )
        log.info(
            f"Registered pending terminal {terminal.public_key_fingerprint} with terminal key "
            f"#{api_key_id}."
        )
        return terminal

    async def _check_terminal_key(self, raw_key: str | None) -> int:
        """The id of a valid terminal key, which holds exactly the connect
        permission."""
        if not raw_key:
            raise TerminalKeyRequiredError("An unknown display needs a terminal key to register.")
        try:
            user, key_id = await ValidateApiKey(
                key_repo=self._keys, user_repo=self._users, hash_fn=hash_api_key
            ).execute(raw_key)
        except (InvalidTokenError, UserNotFoundError, InactiveUserError) as e:
            raise InvalidTerminalKeyError(f"The terminal key is not valid: {e}") from e
        if sorted(user.permissions) != sorted(TERMINAL_KEY_SCOPES):
            raise NotATerminalKeyError("This API key is not a terminal key.")
        return key_id

    async def _refresh_known(self, terminal: Terminal, now: datetime) -> None:
        """A revoked display goes back to pending; a pending one whose code
        expired gets a new code."""
        if terminal.status == TerminalStatus.REVOKED.value:
            terminal_rules.assert_pending_capacity(await self._terminals.count_active_pending(now))
            terminal_rules.return_to_pending(
                terminal, await self._terminals.get_pending_pairing_codes(), now
            )
            log.info(f"Revoked terminal #{terminal.id} signed in again and waits for approval.")
            return
        if terminal.status == TerminalStatus.PENDING.value and terminal_rules.pairing_code_expired(
            terminal, now
        ):
            taken = await self._terminals.get_pending_pairing_codes()
            taken.discard(terminal.pairing_code or "")
            terminal_rules.issue_pairing_code(terminal, taken, now)

    @staticmethod
    def _record_telemetry(
        terminal: Terminal, cmd: StartTerminalSessionCommand, now: datetime
    ) -> None:
        terminal.last_seen_at = now
        terminal.changed = now
        terminal.last_ip = cmd.client_ip
        terminal.user_agent = cmd.user_agent
        terminal.screen_width = cmd.screen_width
        terminal.screen_height = cmd.screen_height
        terminal.frontend_version = cmd.frontend_version
        terminal.bridge_version = cmd.bridge_version
        if cmd.device is not None:
            terminal.device = parse_device_details(cmd.device)
            terminal.device_reported_at = now
