"""
Fixtures exposing the shared fakes (tests/unit/fakes.py) for new unit tests.
See that module's docstring for the promotion rationale and migration policy.
"""

import pytest

from tests.unit.fakes import FakeEventBus
from tests.unit.fakes import FakeUnitOfWork


@pytest.fixture
def fake_uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def fake_event_bus() -> FakeEventBus:
    return FakeEventBus()
