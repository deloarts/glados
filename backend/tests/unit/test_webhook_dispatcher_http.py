"""
HttpxWebhookDispatcher against a real local HTTP and HTTPS server. The
receiver's hostname is mapped to 127.0.0.1 by a fake target guard, which is
how these tests see the pinning: the request reaches the guard's address
while the Host header and the TLS certificate check keep the hostname. They
also cover the Standard Webhooks signature, that the response body is never
read, that redirects are not followed and that a refused target never gets
a request.
"""

import base64
import hashlib
import hmac
import socket
import ssl
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from src.modules.platform.adapters.outbound.external.webhook.httpx_webhook_dispatcher import (
    HttpxWebhookDispatcher,
)
from src.modules.platform.adapters.outbound.external.webhook.httpx_webhook_dispatcher import (
    sign_payload,
)
from src.modules.platform.adapters.outbound.external.webhook.webhook_target_guard import (
    WebhookTargetGuard,
)
from src.modules.platform.domain.exceptions import InvalidWebhookConfigurationError
from src.modules.platform.ports.outbound.webhook_target_guard_port import WebhookTarget

_HUGE = 50 * 1024 * 1024
_SECRET = "whsec_" + base64.b64encode(b"k" * 32).decode()


@dataclass
class _Received:
    requests: list[tuple[str, dict[str, str], bytes]] = field(default_factory=list)
    body_bytes_written: int = 0


class _Handler(BaseHTTPRequestHandler):
    received: ClassVar[_Received] = _Received()
    mode: ClassVar[str] = "huge"

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers["Content-Length"]))
        type(self).received.requests.append((self.path, dict(self.headers), body))
        if type(self).mode == "redirect":
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:1/elsewhere")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(202)
        self.send_header("Content-Length", str(_HUGE))
        self.end_headers()
        chunk = b"x" * 65536
        try:
            for _ in range(_HUGE // len(chunk)):
                self.wfile.write(chunk)
                type(self).received.body_bytes_written += len(chunk)
        except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
            pass

    def log_message(self, *args: object) -> None:
        return None


class _PinningGuard:
    """Resolves every allowed hostname to 127.0.0.1, or refuses."""

    def __init__(self, refuse: bool = False) -> None:
        self.refuse = refuse
        self.calls: list[tuple[str, bool]] = []

    async def resolve(self, url: str, *, allow_private: bool) -> WebhookTarget:
        self.calls.append((url, allow_private))
        if self.refuse:
            raise InvalidWebhookConfigurationError("Webhook host 'receiver.test' is refused.")
        return WebhookTarget(host="receiver.test", addresses=("127.0.0.1",))


def _serve(server: ThreadingHTTPServer) -> Iterator[int]:
    _Handler.received = _Received()
    _Handler.mode = "huge"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


@pytest.fixture
def http_port() -> Iterator[int]:
    yield from _serve(ThreadingHTTPServer(("127.0.0.1", 0), _Handler))


@dataclass
class _Pki:
    client_context: ssl.SSLContext
    cert_dir: Path


def _issue(ca_key: ec.EllipticCurvePrivateKey, ca_name: x509.Name, host: str, out: Path) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)]))
        .issuer_name(ca_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    (out / f"{host}.pem").write_bytes(
        cert.public_bytes(serialization.Encoding.PEM)
        + key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )


@pytest.fixture(scope="module")
def pki(tmp_path_factory: pytest.TempPathFactory) -> _Pki:
    """A throwaway CA with leaf certificates for receiver.test and
    other.test, and a client context that trusts only that CA."""
    out = tmp_path_factory.mktemp("pki")
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Glados test CA")])
    now = datetime.now(UTC)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False
        )
        .sign(ca_key, hashes.SHA256())
    )
    for host in ("receiver.test", "other.test"):
        _issue(ca_key, ca_name, host, out)
    context = ssl.create_default_context(
        cadata=ca_cert.public_bytes(serialization.Encoding.PEM).decode()
    )
    return _Pki(client_context=context, cert_dir=out)


def _https_server(pki: _Pki, host: str) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(pki.cert_dir / f"{host}.pem")
    server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


async def _post(
    dispatcher: HttpxWebhookDispatcher, url: str, secret: str = _SECRET, payload: str = "{}"
):
    return await dispatcher.post(
        url=url,
        secret=secret,
        event_type="LotCreated",
        delivery_id="1700000000000-0",
        payload=payload,
        allow_private=True,
        timeout_seconds=5,
    )


async def test_pins_the_guard_address_and_keeps_the_hostname(http_port: int) -> None:
    guard = _PinningGuard()
    result = await _post(HttpxWebhookDispatcher(guard), f"http://receiver.test:{http_port}/hook")

    assert result.http_status == 202
    assert result.error is None
    ((path, headers, _),) = _Handler.received.requests
    assert path == "/hook"
    assert headers["Host"] == f"receiver.test:{http_port}"
    assert headers["X-Glados-Event"] == "LotCreated"
    assert guard.calls == [(f"http://receiver.test:{http_port}/hook", True)]
    assert _Handler.received.body_bytes_written < _HUGE


async def test_signs_id_timestamp_and_body_the_standard_webhooks_way(http_port: int) -> None:
    payload = '{"id": "1700000000000-0", "event": "LotCreated"}'
    await _post(
        HttpxWebhookDispatcher(_PinningGuard()),
        f"http://receiver.test:{http_port}/hook",
        payload=payload,
    )

    ((_, headers, body),) = _Handler.received.requests
    assert body.decode() == payload
    message_id = headers["webhook-id"]
    timestamp = headers["webhook-timestamp"]
    assert message_id == "1700000000000-0"
    assert abs(int(timestamp) - datetime.now(UTC).timestamp()) < 60

    # Verified the way a receiver following the specification does it.
    key = base64.b64decode(_SECRET.removeprefix("whsec_"))
    expected = base64.b64encode(
        hmac.new(key, f"{message_id}.{timestamp}.".encode() + body, hashlib.sha256).digest()
    ).decode()
    versions = dict(part.split(",", 1) for part in headers["webhook-signature"].split(" "))
    assert hmac.compare_digest(versions["v1"], expected)
    assert "X-Glados-Signature" not in headers


def test_a_hex_secret_from_before_the_whsec_format_still_signs() -> None:
    """Secrets created before the `whsec_` prefix are 64 hex characters,
    which is valid base64, so the same rule applies to them unchanged."""
    secret = "ab" * 32
    signature = sign_payload(secret, "1-0", 1700000000, "{}")
    key = base64.b64decode(secret)
    expected = base64.b64encode(hmac.new(key, b"1-0.1700000000.{}", hashlib.sha256).digest())
    assert signature == f"v1,{expected.decode()}"


async def test_https_verifies_the_certificate_against_the_hostname(pki: _Pki) -> None:
    for port in _serve(_https_server(pki, "receiver.test")):
        result = await _post(
            HttpxWebhookDispatcher(_PinningGuard(), verify=pki.client_context),
            f"https://receiver.test:{port}/hook",
        )
        assert result.error is None
        assert result.http_status == 202
        ((_, headers, _),) = _Handler.received.requests
        assert headers["Host"] == f"receiver.test:{port}"


async def test_https_refuses_a_certificate_for_another_hostname(pki: _Pki) -> None:
    for port in _serve(_https_server(pki, "other.test")):
        result = await _post(
            HttpxWebhookDispatcher(_PinningGuard(), verify=pki.client_context),
            f"https://receiver.test:{port}/hook",
        )
        assert result.http_status is None
        assert result.error == "TLS handshake or certificate verification failed."
        assert _Handler.received.requests == []


async def test_redirects_are_not_followed(http_port: int) -> None:
    _Handler.mode = "redirect"
    result = await _post(
        HttpxWebhookDispatcher(_PinningGuard()), f"http://receiver.test:{http_port}/hook"
    )

    assert result.http_status == 302
    assert len(_Handler.received.requests) == 1


async def test_a_refused_target_never_gets_a_request(http_port: int) -> None:
    result = await _post(
        HttpxWebhookDispatcher(_PinningGuard(refuse=True)),
        f"http://receiver.test:{http_port}/hook",
    )

    assert result.http_status is None
    assert result.error is not None and result.error.startswith("Refused: ")
    assert _Handler.received.requests == []


async def test_the_real_guard_refuses_loopback_at_delivery(http_port: int) -> None:
    result = await _post(
        HttpxWebhookDispatcher(WebhookTargetGuard()), f"http://127.0.0.1:{http_port}/hook"
    )

    assert result.http_status is None
    assert result.error is not None and "never sends webhooks to" in result.error
    assert _Handler.received.requests == []


def _closed_port() -> int:
    """A loopback port nothing listens on, freed right before use, so the
    connection is refused at once. A fixed port such as 9 is not safe: some
    hosts drop packets to it, and the request then times out instead."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    return port


async def test_an_unreachable_receiver_is_recorded_without_the_raw_error() -> None:
    result = await _post(
        HttpxWebhookDispatcher(_PinningGuard()), f"http://receiver.test:{_closed_port()}/hook"
    )

    assert result.http_status is None
    assert result.error == "Connection failed."


async def test_unreadable_secret_fails_the_delivery_without_sending() -> None:
    guard = _PinningGuard()
    result = await _post(HttpxWebhookDispatcher(guard), "http://receiver.test/x", secret="")

    assert result.http_status is None
    assert result.error is not None and "SECURITY__ENCRYPTION_KEY" in result.error
    assert guard.calls == []


async def test_malformed_secret_fails_the_delivery_without_sending() -> None:
    guard = _PinningGuard()
    result = await _post(HttpxWebhookDispatcher(guard), "http://receiver.test/x", secret="whsec_!")

    assert result.http_status is None
    assert result.error == "Signing secret is malformed, recreate the subscription."
    assert guard.calls == []
