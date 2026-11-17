"""
The client address behind the release stack's two proxies. The frontend's
nginx resolves it from X-Forwarded-For only for the proxies listed in
GLADOS_TRUSTED_PROXIES (frontend/docker/trusted-proxies.sh writes them) and
forwards only that address. Gunicorn and uvicorn then resolve
request.client from X-Forwarded-For only for the peers in
NETWORK__TRUSTED_PROXIES (gunicorn_conf.py), which docker-compose.yml sets to
the pinned network nginx connects from. These tests run the script, push
scopes through uvicorn's proxy header handling with the configured trust, and
pin the nginx and compose settings the chain depends on, since neither file
runs anywhere else in the suite.
"""

import importlib
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from gunicorn.config import validate_string_to_addr_list
from pydantic import ValidationError
from uvicorn import Config

from src.modules.platform.infrastructure import gunicorn_conf
from src.modules.platform.infrastructure.config.settings import NetworkSettings

REPO_ROOT = Path(__file__).resolve().parents[3]
TRUSTED_PROXIES_SCRIPT = REPO_ROOT / "frontend" / "docker" / "trusted-proxies.sh"
NGINX_CONF = REPO_ROOT / "frontend" / "docker" / "nginx.conf"
FRONTEND_DOCKERFILE = REPO_ROOT / "frontend" / "docker" / "frontend.Dockerfile"
RELEASE_COMPOSE = REPO_ROOT / "docker-compose.yml"

STACK_NETWORK = "192.168.241.0/24"
NGINX_PEER = "192.168.241.3"
OUTSIDE_PEER = "203.0.113.7"


# ── nginx: trusted proxy list ───────────────────────────────────────────


def _write_trusted_proxies(tmp_path: Path, value: str | None) -> subprocess.CompletedProcess[str]:
    env = {key: val for key, val in os.environ.items() if key != "GLADOS_TRUSTED_PROXIES"}
    if value is not None:
        env["GLADOS_TRUSTED_PROXIES"] = value
    return subprocess.run(
        ["sh", str(TRUSTED_PROXIES_SCRIPT), str(tmp_path / "trusted-proxies.conf")],
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.mark.parametrize("value", [None, "", "none", " none "])
def test_no_trusted_proxy_writes_an_empty_list(tmp_path, value):
    result = _write_trusted_proxies(tmp_path, value)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "trusted-proxies.conf").read_text() == ""


def test_each_listed_proxy_becomes_one_set_real_ip_from_line(tmp_path):
    result = _write_trusted_proxies(tmp_path, "192.168.241.0/24, 10.0.0.1,fd00::/8")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "trusted-proxies.conf").read_text().splitlines() == [
        "set_real_ip_from 192.168.241.0/24;",
        "set_real_ip_from 10.0.0.1;",
        "set_real_ip_from fd00::/8;",
    ]


@pytest.mark.parametrize("entry", ["10.0.0.1;evil", "all", "10.0.0.0/8}"])
def test_a_malformed_entry_stops_the_container(tmp_path, entry):
    result = _write_trusted_proxies(tmp_path, f"192.168.241.0/24,{entry}")

    assert result.returncode != 0
    assert entry in result.stderr


def test_the_image_runs_the_script_and_nginx_includes_its_output():
    dockerfile = FRONTEND_DOCKERFILE.read_text()
    script_default = re.search(r"conf=\$\{1:-([^}]+)\}", TRUSTED_PROXIES_SCRIPT.read_text())

    assert script_default is not None
    assert "docker/trusted-proxies.sh /docker-entrypoint.d/" in dockerfile
    assert f"include            {script_default.group(1)};" in NGINX_CONF.read_text()


# ── nginx: client address and forwarded headers ─────────────────────────


def test_nginx_resolves_the_client_from_the_rightmost_untrusted_hop():
    conf = NGINX_CONF.read_text()

    assert "real_ip_header     X-Forwarded-For;" in conf
    assert "real_ip_recursive  on;" in conf


def test_nginx_replaces_x_forwarded_for_instead_of_appending():
    conf = NGINX_CONF.read_text()
    forwarded = re.findall(r"proxy_set_header\s+X-Forwarded-For\s+(\S+);", conf)

    assert "$proxy_add_x_forwarded_for" not in conf
    assert forwarded
    assert set(forwarded) == {"$remote_addr"}


def test_the_rate_limit_keys_on_the_resolved_client_address():
    conf = NGINX_CONF.read_text()

    assert re.search(r"limit_req_zone\s+\$binary_remote_addr\s", conf)
    assert "$http_x_forwarded_for" not in conf


# ── backend: forwarded header trust ─────────────────────────────────────


def _trusted_peers(monkeypatch, value: str | None) -> Any:
    """The validated forwarded_allow_ips gunicorn hands the uvicorn worker
    when the environment carries `value`."""
    try:
        with monkeypatch.context() as patch:
            if value is None:
                patch.delenv("NETWORK__TRUSTED_PROXIES", raising=False)
            else:
                patch.setenv("NETWORK__TRUSTED_PROXIES", value)
            conf = importlib.reload(gunicorn_conf)
            return validate_string_to_addr_list(conf.forwarded_allow_ips)
    finally:
        importlib.reload(gunicorn_conf)


async def _resolve(trusted: Any, peer: str, headers: dict[str, str]) -> tuple[str, str]:
    """Runs one request scope through uvicorn's proxy header handling, as the
    worker configures it, and returns the client host and scheme it ends
    with."""
    seen: dict[str, Any] = {}

    async def app(scope, receive, send):
        seen.update(scope)

    config = Config(app, forwarded_allow_ips=trusted, log_config=None)
    config.load()
    scope = {
        "type": "http",
        "scheme": "http",
        "client": (peer, 40000),
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    await config.loaded_app(scope, None, None)
    return seen["client"][0], seen["scheme"]


def test_without_the_setting_only_loopback_is_trusted(monkeypatch):
    assert _trusted_peers(monkeypatch, None) == ["127.0.0.1", "::1"]


def test_a_malformed_trusted_proxy_is_refused(monkeypatch):
    with pytest.raises(ValueError):
        _trusted_peers(monkeypatch, "192.168.241.0/24,not-an-address")


async def test_a_trusted_peer_forwards_the_client_and_scheme(monkeypatch):
    trusted = _trusted_peers(monkeypatch, STACK_NETWORK)

    host, scheme = await _resolve(
        trusted, NGINX_PEER, {"X-Forwarded-For": "198.51.100.20", "X-Forwarded-Proto": "https"}
    )

    assert (host, scheme) == ("198.51.100.20", "https")


async def test_an_untrusted_peer_cannot_choose_its_address(monkeypatch):
    trusted = _trusted_peers(monkeypatch, STACK_NETWORK)

    host, scheme = await _resolve(
        trusted, OUTSIDE_PEER, {"X-Forwarded-For": "10.1.2.3", "X-Forwarded-Proto": "https"}
    )

    assert (host, scheme) == (OUTSIDE_PEER, "http")


async def test_a_prepended_hop_is_ignored(monkeypatch):
    trusted = _trusted_peers(monkeypatch, STACK_NETWORK)

    host, _ = await _resolve(trusted, NGINX_PEER, {"X-Forwarded-For": "10.1.2.3, 198.51.100.20"})

    assert host == "198.51.100.20"


async def test_the_default_trust_ignores_the_frontend_container(monkeypatch):
    trusted = _trusted_peers(monkeypatch, None)

    host, _ = await _resolve(trusted, NGINX_PEER, {"X-Forwarded-For": "198.51.100.20"})

    assert host == NGINX_PEER


# ── backend: the stack's own networks ───────────────────────────────────


def test_internal_subnets_read_a_comma_separated_list(monkeypatch):
    monkeypatch.setenv("NETWORK__INTERNAL_SUBNETS", "192.168.240.0/24, 192.168.241.0/24")

    from src.modules.platform.infrastructure.config.settings import Settings

    subnets = Settings().network.internal_subnets  # type: ignore[call-arg]

    assert [str(net) for net in subnets] == ["192.168.240.0/24", "192.168.241.0/24"]


def test_internal_subnets_default_to_none():
    assert NetworkSettings().internal_subnets == ()


def test_an_internal_subnet_with_host_bits_is_refused():
    with pytest.raises(ValidationError):
        NetworkSettings(internal_subnets="192.168.240.1/24")  # type: ignore[arg-type]


# ── compose ─────────────────────────────────────────────────────────────


def _compose() -> dict[str, Any]:
    return yaml.safe_load(RELEASE_COMPOSE.read_text())


def test_no_image_defaults_to_latest():
    text = RELEASE_COMPOSE.read_text()

    assert ":-latest}" not in text
    services = _compose()["services"]
    for name in ("backend", "maintenance", "frontend"):
        assert "${GLADOS_VERSION:?" in services[name]["image"], name
    assert "@sha256:" in services["postgres"]["image"]


def test_both_networks_have_a_pinned_subnet():
    networks = _compose()["networks"]

    assert networks["internal"]["ipam"]["config"][0]["subnet"].startswith(
        "${GLADOS_INTERNAL_SUBNET:-"
    )
    assert networks["external"]["ipam"]["config"][0]["subnet"].startswith(
        "${GLADOS_EXTERNAL_SUBNET:-"
    )


def test_the_backend_trusts_only_the_network_nginx_connects_from():
    services = _compose()["services"]

    assert "external" in services["frontend"]["networks"]
    assert "internal" not in services["frontend"]["networks"]
    assert services["backend"]["environment"]["NETWORK__TRUSTED_PROXIES"].startswith(
        "${GLADOS_EXTERNAL_SUBNET:-"
    )
    assert "--forwarded-allow-ips" not in services["backend"]["command"]
