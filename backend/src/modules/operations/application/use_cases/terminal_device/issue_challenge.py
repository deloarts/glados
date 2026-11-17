"""
The first step of a device sign-in: a single-use nonce the device's bridge
signs with its private key. Needs no credential, so it is rate-limited per
client address and refused while terminals are switched off or the address
is not on the terminal allowlist.
"""

from src.modules.operations.application.dto.terminal_dto import TerminalChallengeResult
from src.modules.operations.application.services.terminal_auth_rate_limiter import (
    TerminalAuthRateLimiter,
)
from src.modules.operations.domain.errors import TerminalChallengeError
from src.modules.operations.domain.services import terminal_rules
from src.modules.operations.domain.value_objects.terminal import TERMINAL_CHALLENGE_TTL_SECONDS
from src.modules.operations.infrastructure.security.terminal_auth import is_valid_public_key
from src.modules.operations.infrastructure.security.terminal_auth import issue_nonce
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.shared_kernel.domain.services.clock import now_utc


class IssueTerminalChallenge:
    def __init__(
        self, settings_repo: IOperationsSettingsRepository, rate_limiter: TerminalAuthRateLimiter
    ) -> None:
        self._settings = settings_repo
        self._limiter = rate_limiter

    async def execute(self, public_key: str, client_ip: str | None) -> TerminalChallengeResult:
        terminal_rules.assert_access_allowed(await self._settings.get_security(), client_ip)
        self._limiter.check("challenge", client_ip)
        if not is_valid_public_key(public_key):
            raise TerminalChallengeError("The public key is not a raw Ed25519 key in base64url.")
        nonce, expires_at = issue_nonce(public_key, now_utc(), TERMINAL_CHALLENGE_TTL_SECONDS)
        return TerminalChallengeResult(nonce=nonce, expires_at=expires_at)
