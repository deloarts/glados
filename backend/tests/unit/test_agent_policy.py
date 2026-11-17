"""
The rules of the MCP surface (domain/services/agent_policy.py) and the
resolver that builds a tool's use case through its route's factory.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

import pytest
from fastapi import Depends
from fastapi import Header

from src.modules.platform.adapters.inbound.api.deps.database import get_db
from src.modules.platform.adapters.inbound.mcp.resolve import DependencyResolver
from src.modules.platform.adapters.inbound.mcp.resolve import UnresolvableDependencyError
from src.modules.platform.domain.services.agent_policy import REDACTED
from src.modules.platform.domain.services.agent_policy import agent_token_lifetime_cap
from src.modules.platform.domain.services.agent_policy import is_cost_key
from src.modules.platform.domain.services.agent_policy import is_idle
from src.modules.platform.domain.services.agent_policy import is_person_key
from src.modules.platform.domain.services.agent_policy import normalise_allowed_origins
from src.modules.platform.domain.services.agent_policy import origin_allowed
from src.modules.platform.domain.services.agent_policy import redact

_T0 = datetime(2026, 11, 1, tzinfo=UTC)

# ── Origins ───────────────────────────────────────────────────────────


def test_allowed_origins_normalise_case_slash_and_duplicates() -> None:
    assert normalise_allowed_origins(
        [" https://Glados.example.com/ ", "https://glados.example.com", "", "http://localhost:5173"]
    ) == ["https://glados.example.com", "http://localhost:5173"]


@pytest.mark.parametrize(
    "entry", ["glados.example.com", "ftp://glados", "https://glados/app", "https://g?x=1"]
)
def test_allowed_origins_refuse_anything_but_a_bare_origin(entry: str) -> None:
    with pytest.raises(ValueError):
        normalise_allowed_origins([entry])


def test_origin_allowed_passes_agent_clients_and_listed_browsers_only() -> None:
    allowed = ["https://glados.example.com"]

    assert origin_allowed(None, allowed)
    assert origin_allowed("https://GLADOS.example.com/", allowed)
    assert not origin_allowed("https://evil.example.com", allowed)
    assert not origin_allowed("https://glados.example.com", [])


# ── Token lifetime ────────────────────────────────────────────────────


@pytest.mark.parametrize(("general", "agent", "cap"), [(0, 30, 30), (3650, 30, 30), (7, 30, 7)])
def test_agent_token_cap_is_the_stricter_one_and_never_lifted(
    general: int, agent: int, cap: int
) -> None:
    assert agent_token_lifetime_cap(general, agent) == cap


def test_token_is_idle_from_its_last_call_or_its_creation() -> None:
    assert is_idle(_T0, None, _T0 + timedelta(days=14), 14)
    assert not is_idle(_T0, None, _T0 + timedelta(days=13), 14)
    assert not is_idle(_T0, _T0 + timedelta(days=10), _T0 + timedelta(days=20), 14)
    # A call recorded before the creation (a clock skew) counts as none.
    assert is_idle(_T0, _T0 - timedelta(days=1), _T0 + timedelta(days=14), 14)


# ── Redaction ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "key", ["full_name", "operator_full_name", "username", "actor_username", "email", "phone"]
)
def test_person_keys(key: str) -> None:
    assert is_person_key(key)


@pytest.mark.parametrize("key", ["user_id", "name", "part_name", "machine_name", "created_by_id"])
def test_not_person_keys(key: str) -> None:
    assert not is_person_key(key)


@pytest.mark.parametrize(
    "key", ["unit_price", "price", "extra_costs", "total_cost", "currency", "net_amount"]
)
def test_cost_keys(key: str) -> None:
    assert is_cost_key(key)


@pytest.mark.parametrize(
    "key", ["priority", "value", "total", "quantity_total", "cost_center_hours", "amount_count"]
)
def test_not_cost_keys(key: str) -> None:
    assert not is_cost_key(key)


def test_redact_hides_names_and_drops_money_in_nested_results() -> None:
    result: dict[str, Any] = {
        "lot": {"number": "L-1", "operator_full_name": "Anna", "assignee": None},
        "lines": [{"part": "4711", "unit_price": 3.5, "created_by": {"id": 2, "username": "a"}}],
        "full_name": None,
    }

    cleaned = redact(result, include_person_names=False, include_costs=False)

    assert cleaned == {
        "lot": {"number": "L-1", "operator_full_name": REDACTED, "assignee": None},
        "lines": [{"part": "4711", "created_by": {"id": 2, "username": REDACTED}}],
        "full_name": None,
    }


def test_redact_keeps_everything_when_the_settings_allow_it() -> None:
    result = {"operator_full_name": "Anna", "unit_price": 3.5}

    assert redact(result, include_person_names=True, include_costs=True) == result


# ── Resolver ──────────────────────────────────────────────────────────


class _Repo:
    def __init__(self, db: object) -> None:
        self.db = db


def _repo(db: object = Depends(get_db)) -> _Repo:
    return _Repo(db)


async def _async_service(repo: _Repo = Depends(_repo)) -> tuple[_Repo, str]:
    return repo, "service"


def _use_case(
    repo: _Repo = Depends(_repo),
    service: tuple[_Repo, str] = Depends(_async_service),
    flag: bool = True,
) -> tuple[_Repo, tuple[_Repo, str], bool]:
    return repo, service, flag


async def test_resolver_hands_out_the_session_and_builds_each_dependency_once() -> None:
    session = object()

    repo, (service_repo, label), flag = await DependencyResolver(session).build(  # type: ignore[arg-type]
        _use_case
    )

    assert repo.db is session
    assert service_repo is repo
    assert (label, flag) == ("service", True)


async def test_resolver_applies_overrides() -> None:
    fake = _Repo("fake")

    repo, _, _ = await DependencyResolver(object(), {_repo: lambda: fake}).build(  # type: ignore[arg-type]
        _use_case
    )

    assert repo is fake


def _needs_header(token: str = Header()) -> str:
    return token


def _needs_header_indirectly(value: str = Depends(_needs_header)) -> str:
    return value


async def test_resolver_refuses_a_factory_that_reads_the_request() -> None:
    with pytest.raises(UnresolvableDependencyError, match="_needs_header"):
        await DependencyResolver(object()).build(_needs_header_indirectly)  # type: ignore[arg-type]


def test_redact_drops_free_text_histories_unless_names_and_money_may_leave() -> None:
    result = {"part": "4711", "changes": ["Price 3 -> 4 by Anna"]}

    assert redact(result, include_person_names=False, include_costs=True) == {"part": "4711"}
    assert redact(result, include_person_names=True, include_costs=False) == {"part": "4711"}
    assert redact(result, include_person_names=True, include_costs=True) == result


@pytest.mark.parametrize("key", ["planned_by_name", "ordered_by_name", "checked_by_name"])
def test_who_did_it_keys_name_a_person(key: str) -> None:
    assert is_person_key(key)


@pytest.mark.parametrize("key", ["net_total", "lines_total", "spend"])
def test_order_sums_are_money(key: str) -> None:
    assert is_cost_key(key)
