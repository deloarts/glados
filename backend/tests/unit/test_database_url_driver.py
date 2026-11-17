"""
DatabaseSettings keeps the configured URL as it is, so the env file names
the driver.
"""

import pytest

from src.modules.platform.infrastructure.config.settings import DatabaseSettings


def _url(value: str) -> str:
    return DatabaseSettings(url=value).url


@pytest.mark.parametrize(
    "unchanged",
    ["postgresql+psycopg://glados:pw@postgres:5432/glados", "sqlite:////tmp/test.db"],
)
def test_other_urls_are_left_alone(unchanged: str) -> None:
    assert _url(unchanged) == unchanged
