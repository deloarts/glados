"""
WebhookTargetGuard, the policy every webhook URL passes when a subscription
is saved and before every delivery. DNS is replaced by a fake resolver, so
each case states exactly which addresses a hostname resolves to.
"""

import asyncio
from collections.abc import Sequence
from ipaddress import ip_network

import pytest

from src.modules.platform.adapters.outbound.external.webhook.webhook_target_guard import (
    WebhookTargetGuard,
)
from src.modules.platform.domain.exceptions import InvalidWebhookConfigurationError

_INTERNAL = (ip_network("192.168.240.0/24"), ip_network("fd00:6c::/64"))


def _guard(answers: dict[str, Sequence[str]] | None = None) -> WebhookTargetGuard:
    table = answers or {}

    async def resolve(host: str, port: int) -> Sequence[str]:
        if host not in table:
            raise OSError("no such host")
        return table[host]

    return WebhookTargetGuard(_INTERNAL, resolver=resolve)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/hook",
        "http://127.8.9.10/hook",
        "http://[::1]/hook",
        "http://0.0.0.0/hook",
        "http://0.1.2.3/hook",
        "http://[::]/hook",
        "http://169.254.169.254/latest/meta-data/",
        "http://[fe80::1]/hook",
        "http://224.0.0.1/hook",
        "http://[ff02::1]/hook",
        "http://240.0.0.1/hook",
        "http://255.255.255.255/hook",
        "http://[::ffff:127.0.0.1]/hook",
        "http://[::ffff:169.254.169.254]/hook",
        "http://192.168.240.7/hook",
        "http://[fd00:6c::5]/hook",
        "http://[::ffff:192.168.240.7]/hook",
    ],
)
async def test_literal_addresses_in_the_always_refused_set_are_refused(url: str) -> None:
    with pytest.raises(InvalidWebhookConfigurationError, match="never sends webhooks to"):
        await _guard().resolve(url, allow_private=True)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/hook",
        "http://LOCALHOST./hook",
        "http://api.localhost/hook",
        "http://redis:6379/",
        "http://Postgres:5432/",
        "http://backend:3000/api",
        "http://frontend/",
        "http://seaweedfs:8333/",
        "http://pgadmin/",
        "http://maintenance/",
    ],
)
async def test_localhost_and_the_stack_service_names_are_refused_without_resolving(
    url: str,
) -> None:
    async def must_not_resolve(host: str, port: int) -> Sequence[str]:
        raise AssertionError(f"{host} was resolved")

    guard = WebhookTargetGuard(_INTERNAL, resolver=must_not_resolve)
    with pytest.raises(InvalidWebhookConfigurationError, match="never sends webhooks to"):
        await guard.resolve(url, allow_private=True)


async def test_a_hostname_resolving_into_the_internal_subnet_is_refused() -> None:
    guard = _guard({"hooks.example.com": ["192.168.240.3"]})
    with pytest.raises(InvalidWebhookConfigurationError, match="never sends webhooks to"):
        await guard.resolve("https://hooks.example.com/x", allow_private=True)


async def test_every_resolved_address_must_pass_not_just_the_first() -> None:
    guard = _guard({"hooks.example.com": ["93.184.215.14", "127.0.0.1"]})
    with pytest.raises(InvalidWebhookConfigurationError):
        await guard.resolve("https://hooks.example.com/x", allow_private=True)


async def test_the_refusal_names_the_host_but_never_the_resolved_address() -> None:
    guard = _guard({"hooks.example.com": ["169.254.169.254"]})
    with pytest.raises(InvalidWebhookConfigurationError) as caught:
        await guard.resolve("https://hooks.example.com/x", allow_private=True)
    assert "hooks.example.com" in str(caught.value)
    assert "169.254" not in str(caught.value)


@pytest.mark.parametrize(
    "address", ["10.0.0.5", "172.16.0.5", "192.168.1.5", "fd12:3456::1", "100.64.0.1"]
)
async def test_private_ranges_follow_the_setting(address: str) -> None:
    guard = _guard({"erp.corp.example": [address]})

    target = await guard.resolve("https://erp.corp.example/hook", allow_private=True)
    assert target.addresses == (address,)

    with pytest.raises(InvalidWebhookConfigurationError, match="private network"):
        await guard.resolve("https://erp.corp.example/hook", allow_private=False)


async def test_a_public_host_passes_and_keeps_every_address_in_order() -> None:
    guard = _guard(
        {"hooks.example.com": ["93.184.215.14", "2606:2800:21f:cb07:6820:80da:af6b:8b2c"]}
    )

    target = await guard.resolve("https://Hooks.Example.com.:8443/x", allow_private=False)

    assert target.host == "hooks.example.com"
    assert target.addresses == ("93.184.215.14", "2606:2800:21f:cb07:6820:80da:af6b:8b2c")


async def test_an_international_hostname_is_resolved_in_its_ascii_form() -> None:
    guard = _guard({"xn--r8jz45g.jp": ["93.184.215.14"]})
    target = await guard.resolve("https://例え.jp/hook", allow_private=False)
    assert target.host == "xn--r8jz45g.jp"


async def test_an_unresolvable_host_is_refused() -> None:
    with pytest.raises(InvalidWebhookConfigurationError, match="could not be resolved"):
        await _guard().resolve("https://nowhere.example/hook", allow_private=True)


async def test_a_slow_resolver_is_cut_off() -> None:
    async def hang(host: str, port: int) -> Sequence[str]:
        await asyncio.sleep(10)
        return ["93.184.215.14"]

    guard = WebhookTargetGuard((), resolver=hang, resolve_timeout_seconds=0.01)
    with pytest.raises(InvalidWebhookConfigurationError, match="could not be resolved"):
        await guard.resolve("https://slow.example/hook", allow_private=True)


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("ftp://hooks.example.com/x", "http:// or https://"),
        ("file:///etc/passwd", "http:// or https://"),
        ("hooks.example.com/x", "http:// or https://"),
        ("https://user:pass@hooks.example.com/x", "user name or password"),
        ("https://user@hooks.example.com/x", "user name or password"),
        ("https://hooks.example.com:99999/x", "not a valid URL"),
    ],
)
async def test_malformed_urls_are_refused(url: str, message: str) -> None:
    guard = _guard({"hooks.example.com": ["93.184.215.14"]})
    with pytest.raises(InvalidWebhookConfigurationError, match=message):
        await guard.resolve(url, allow_private=True)


async def test_any_port_is_allowed() -> None:
    guard = _guard({"hooks.example.com": ["93.184.215.14"]})
    target = await guard.resolve("http://hooks.example.com:6379/x", allow_private=False)
    assert target.addresses == ("93.184.215.14",)
