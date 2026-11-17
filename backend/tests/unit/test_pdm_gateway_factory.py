"""
create_pdm_gateway shares one gateway, and so one HTTP client, per
connection instead of opening a new client on every call, keeps the cache
bounded, and closes what it holds on shutdown.
"""

import pytest

from src.modules.external_data.adapters.outbound.external.pdm import factory
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConnection


def _connection(n: int = 0) -> PdmConnection:
    return PdmConnection(
        base_url=f"https://pdm{n}.example",
        vault_name="Vault",
        verify_certificate=True,
        timeout_seconds=5,
    )


@pytest.fixture(autouse=True)
async def _empty_cache():
    await factory.close_pdm_gateways()
    yield
    await factory.close_pdm_gateways()


def test_same_connection_reuses_one_gateway() -> None:
    assert factory.create_pdm_gateway(_connection()) is factory.create_pdm_gateway(_connection())


def test_different_connection_gets_its_own_gateway() -> None:
    assert factory.create_pdm_gateway(_connection(1)) is not factory.create_pdm_gateway(
        _connection(2)
    )


def test_cache_is_bounded_and_evicts_least_recently_used() -> None:
    first = factory.create_pdm_gateway(_connection(0))
    newer = [
        factory.create_pdm_gateway(_connection(n))
        for n in range(1, factory.MAX_CACHED_GATEWAYS + 1)
    ]

    # The newest gateways fill the cache and are all still held.
    assert all(
        factory.create_pdm_gateway(_connection(n)) is gateway
        for n, gateway in enumerate(newer, start=1)
    )
    assert factory.create_pdm_gateway(_connection(0)) is not first


async def test_close_closes_every_cached_client() -> None:
    gateways = [factory.create_pdm_gateway(_connection(n)) for n in range(2)]

    await factory.close_pdm_gateways()

    # httpx refuses a request on a closed client before it opens a
    # connection, so a closed gateway fails at once.
    for gateway in gateways:
        with pytest.raises(RuntimeError, match="client has been closed"):
            await gateway.version()
    # The cache is empty, so the same connection builds a new gateway.
    assert factory.create_pdm_gateway(_connection(0)) is not gateways[0]
