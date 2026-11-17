"""
IPasskeyVerifier on top of py_webauthn.

The relying party is derived from `DOMAIN`, the public URL the frontend is
served from: its host name is the relying-party ID passkeys are bound to,
and its origin is the only one a response may come from. Browsers allow
WebAuthn on https origins and on http://localhost, so a plain-http
deployment under any other host name cannot use passkeys. Changing the
host name later orphans every registered passkey.
"""

import json
from typing import Any
from urllib.parse import urlsplit

from webauthn import generate_authentication_options
from webauthn import generate_registration_options
from webauthn import options_to_json
from webauthn import verify_authentication_response
from webauthn import verify_registration_response
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers import parse_registration_credential_json
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import AuthenticatorSelectionCriteria
from webauthn.helpers.structs import PublicKeyCredentialDescriptor
from webauthn.helpers.structs import ResidentKeyRequirement
from webauthn.helpers.structs import UserVerificationRequirement

from src.modules.platform.const import NAME
from src.modules.platform.domain.exceptions import PasskeyRegistrationFailedError
from src.modules.platform.domain.exceptions import PasskeyRejectedError
from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.ports.outbound.passkey_verifier_port import PasskeyOptions
from src.modules.platform.ports.outbound.passkey_verifier_port import VerifiedPasskeyRegistration

# Milliseconds the browser keeps its prompt open.
PROMPT_TIMEOUT_MS = 120_000


def _relying_party(domain: str) -> tuple[str, str]:
    """The relying-party ID (host name) and origin of the public URL."""
    parts = urlsplit(domain.strip())
    return parts.hostname or "localhost", f"{parts.scheme}://{parts.netloc}"


class WebAuthnVerifier:
    def __init__(self, domain: str, rp_name: str = NAME) -> None:
        self._rp_id, self._origin = _relying_party(domain)
        self._rp_name = rp_name

    def registration_options(
        self,
        *,
        user_handle: bytes,
        username: str,
        display_name: str,
        exclude_credential_ids: list[bytes],
    ) -> PasskeyOptions:
        options = generate_registration_options(
            rp_id=self._rp_id,
            rp_name=self._rp_name,
            user_id=user_handle,
            user_name=username,
            user_display_name=display_name or username,
            timeout=PROMPT_TIMEOUT_MS,
            # Discoverable where the authenticator can store it, so the
            # browser can offer the passkey without being told its ID; user
            # verification is required because the passkey stands in for
            # the password and the second factor at once.
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
            exclude_credentials=[
                PublicKeyCredentialDescriptor(id=cid) for cid in exclude_credential_ids
            ],
        )
        return PasskeyOptions(
            options=json.loads(options_to_json(options)),
            challenge=bytes_to_base64url(options.challenge),
        )

    def verify_registration(
        self, *, credential: dict[str, Any], challenge: str
    ) -> VerifiedPasskeyRegistration:
        try:
            parsed = parse_registration_credential_json(credential)
            verified = verify_registration_response(
                credential=parsed,
                expected_challenge=base64url_to_bytes(challenge),
                expected_rp_id=self._rp_id,
                expected_origin=self._origin,
                require_user_verification=True,
            )
        except (WebAuthnException, ValueError, TypeError, KeyError) as exc:
            raise PasskeyRegistrationFailedError(
                f"The passkey registration did not verify: {exc}"
            ) from exc
        return VerifiedPasskeyRegistration(
            credential_id=verified.credential_id,
            public_key=verified.credential_public_key,
            sign_count=verified.sign_count,
            backed_up=verified.credential_backed_up,
            transports=[t.value for t in parsed.response.transports or []],
        )

    def authentication_options(self) -> PasskeyOptions:
        options = generate_authentication_options(
            rp_id=self._rp_id,
            timeout=PROMPT_TIMEOUT_MS,
            user_verification=UserVerificationRequirement.REQUIRED,
        )
        return PasskeyOptions(
            options=json.loads(options_to_json(options)),
            challenge=bytes_to_base64url(options.challenge),
        )

    def credential_id_of(self, credential: dict[str, Any]) -> bytes | None:
        raw_id = credential.get("rawId")
        if not isinstance(raw_id, str) or not raw_id:
            return None
        try:
            return base64url_to_bytes(raw_id)
        except ValueError:
            return None

    def verify_authentication(
        self,
        *,
        credential: dict[str, Any],
        challenge: str,
        public_key: bytes,
        sign_count: int,
    ) -> int:
        try:
            verified = verify_authentication_response(
                credential=credential,
                expected_challenge=base64url_to_bytes(challenge),
                expected_rp_id=self._rp_id,
                expected_origin=self._origin,
                credential_public_key=public_key,
                credential_current_sign_count=sign_count,
                require_user_verification=True,
            )
        except (WebAuthnException, ValueError, TypeError, KeyError) as exc:
            raise PasskeyRejectedError(f"The passkey login did not verify: {exc}") from exc
        return verified.new_sign_count


def default_passkey_verifier() -> WebAuthnVerifier:
    return WebAuthnVerifier(cfg.domain)
