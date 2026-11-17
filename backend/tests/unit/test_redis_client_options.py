"""
The shared async Redis client carries bounded timeouts and pool size from
RedisSettings, with the socket timeout above the event workers' stream
block so an idle XREADGROUP never times out on its own.
"""

from src.modules.platform.infrastructure.config.settings import RedisSettings
from src.modules.platform.infrastructure.events import worker
from src.modules.platform.infrastructure.redis_client import client_options
from src.modules.platform.infrastructure.redis_client import get_async_redis_client
from src.modules.platform.infrastructure.redis_client import new_probe_redis_client


def test_options_follow_settings() -> None:
    options = client_options(
        RedisSettings(url="redis://x", socket_timeout_seconds=4, max_connections=7)
    )

    assert options["socket_timeout"] == 4
    assert options["socket_connect_timeout"] == 2.0
    assert options["max_connections"] == 7
    assert "health_check_interval" not in options


def test_default_socket_timeout_outlasts_the_worker_stream_block() -> None:
    assert RedisSettings(url="redis://x").socket_timeout_seconds * 1000 > worker._BLOCK_MS


def test_shared_client_is_built_with_timeouts_and_retry() -> None:
    client = get_async_redis_client()
    kwargs = client.connection_pool.connection_kwargs
    assert kwargs["socket_timeout"] == 3.0
    assert kwargs["socket_connect_timeout"] == 2.0
    assert client.connection_pool.max_connections == 50
    assert kwargs["retry"].get_retries() == 1


def test_probe_client_never_retries() -> None:
    """redis-py 8 gives a client ten retries by default, which would stretch
    the probe's one-second budget, so the probe client sets zero explicitly
    instead of relying on whichever default the library ships."""
    kwargs = new_probe_redis_client().connection_pool.connection_kwargs
    assert kwargs["socket_timeout"] == 1
    assert kwargs["socket_connect_timeout"] == 1
    assert kwargs["retry"].get_retries() == 0
