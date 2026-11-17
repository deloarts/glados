"""
A software WebAuthn authenticator for tests: it answers the options the
backend hands out with the JSON a browser would send back, signed with a
real P-256 key and attested with the "none" format, so the passkey
routes run through py_webauthn's real verification.
"""

import hashlib
import json
import os
import struct
from base64 import urlsafe_b64decode
from base64 import urlsafe_b64encode
from typing import Any

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

_UP = 0x01  # user present
_UV = 0x04  # user verified
_AT = 0x40  # attested credential data included


def b64url(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64url(value: str) -> bytes:
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


class SoftAuthenticator:
    def __init__(self, origin: str, *, user_verified: bool = True) -> None:
        self.origin = origin
        self.user_verified = user_verified
        self.credential_id = os.urandom(32)
        self.sign_count = 0
        self.user_handle: bytes | None = None
        self._key = ec.generate_private_key(ec.SECP256R1())

    def _flags(self, extra: int = 0) -> int:
        return _UP | (_UV if self.user_verified else 0) | extra

    def _client_data(self, kind: str, challenge: str) -> bytes:
        return json.dumps(
            {"type": kind, "challenge": challenge, "origin": self.origin, "crossOrigin": False}
        ).encode()

    def _cose_public_key(self) -> bytes:
        numbers = self._key.public_key().public_numbers()
        return cbor2.dumps(
            {
                1: 2,  # kty: EC2
                3: -7,  # alg: ES256
                -1: 1,  # crv: P-256
                -2: numbers.x.to_bytes(32, "big"),
                -3: numbers.y.to_bytes(32, "big"),
            }
        )

    def create(self, options: dict[str, Any]) -> dict[str, Any]:
        """The registration response to navigator.credentials.create()."""
        self.user_handle = unb64url(options["user"]["id"])
        rp_id_hash = hashlib.sha256(options["rp"]["id"].encode()).digest()
        attested = (
            bytes(16)  # AAGUID
            + struct.pack(">H", len(self.credential_id))
            + self.credential_id
            + self._cose_public_key()
        )
        auth_data = (
            rp_id_hash + bytes([self._flags(_AT)]) + struct.pack(">I", self.sign_count) + attested
        )
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": b64url(self.credential_id),
            "rawId": b64url(self.credential_id),
            "type": "public-key",
            "authenticatorAttachment": "platform",
            "clientExtensionResults": {},
            "response": {
                "clientDataJSON": b64url(
                    self._client_data("webauthn.create", options["challenge"])
                ),
                "attestationObject": b64url(attestation),
                "transports": ["internal"],
            },
        }

    def get(self, options: dict[str, Any], *, rp_id: str) -> dict[str, Any]:
        """The login response to navigator.credentials.get()."""
        self.sign_count += 1
        client_data = self._client_data("webauthn.get", options["challenge"])
        auth_data = (
            hashlib.sha256(rp_id.encode()).digest()
            + bytes([self._flags()])
            + struct.pack(">I", self.sign_count)
        )
        signature = self._key.sign(
            auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256())
        )
        return {
            "id": b64url(self.credential_id),
            "rawId": b64url(self.credential_id),
            "type": "public-key",
            "authenticatorAttachment": "platform",
            "clientExtensionResults": {},
            "response": {
                "clientDataJSON": b64url(client_data),
                "authenticatorData": b64url(auth_data),
                "signature": b64url(signature),
                "userHandle": b64url(self.user_handle or b""),
            },
        }
