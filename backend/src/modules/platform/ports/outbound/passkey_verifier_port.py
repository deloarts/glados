"""
Abstract WebAuthn ceremony: the options a browser needs to create or use a
passkey, and the verification of what it sends back. The application layer
calls this, never a WebAuthn library directly.
"""

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Protocol
from typing import runtime_checkable


@dataclass(frozen=True)
class PasskeyOptions:
    """`options` is the JSON form of PublicKeyCredentialCreationOptions or
    PublicKeyCredentialRequestOptions, ready for the browser. `challenge`
    is the base64url challenge inside it, which the caller binds to the
    verify request."""

    options: dict[str, Any]
    challenge: str


@dataclass(frozen=True)
class VerifiedPasskeyRegistration:
    credential_id: bytes
    public_key: bytes
    sign_count: int
    backed_up: bool
    transports: list[str] = field(default_factory=list)


@runtime_checkable
class IPasskeyVerifier(Protocol):
    def registration_options(
        self,
        *,
        user_handle: bytes,
        username: str,
        display_name: str,
        exclude_credential_ids: list[bytes],
    ) -> PasskeyOptions:
        """Options for creating a passkey. `exclude_credential_ids` are the
        user's existing passkeys, so the browser refuses to register the same
        authenticator twice."""
        ...

    def verify_registration(
        self, *, credential: dict[str, Any], challenge: str
    ) -> VerifiedPasskeyRegistration:
        """Checks the browser's registration response against `challenge`,
        the origin and the relying party, with user verification required.
        Raises PasskeyRegistrationFailedError when it does not verify."""
        ...

    def authentication_options(self) -> PasskeyOptions:
        """Options for a passkey login. They name no credentials, so the
        response reveals nothing about which accounts hold passkeys; the
        browser narrows the choice itself."""
        ...

    def credential_id_of(self, credential: dict[str, Any]) -> bytes | None:
        """The credential ID a login response claims, or None when the
        response is malformed. Unverified: only good for the lookup."""
        ...

    def verify_authentication(
        self,
        *,
        credential: dict[str, Any],
        challenge: str,
        public_key: bytes,
        sign_count: int,
    ) -> int:
        """Checks a login response's signature against the stored public
        key, `challenge`, the origin and the relying party, with user
        verification required. Returns the authenticator's new signature
        counter. Raises PasskeyRejectedError when it does not verify, which
        includes a counter that went backwards (a cloned authenticator)."""
        ...
